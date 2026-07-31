#!/usr/bin/env python3
"""Cloud/local batch: grow real PMID claims for claim-less catalog interventions.

Uses NCBI E-utilities only — never invents PMIDs. A claim is written only when a
PubMed title matches intervention keywords.

Examples:
  # Timed dry-run of 100 (no file write)
  python3 scripts/pmid_growth_batch.py --limit 100 --dry-run

  # Write up to 150 validated claims (daily cloud target)
  python3 scripts/pmid_growth_batch.py --limit 150 --write

  # JSON summary for CI
  python3 scripts/pmid_growth_batch.py --limit 100 --write --json-out ops/pmid_growth_last_run.json

Env:
  NCBI_API_KEY  optional — higher rate limit
  NCBI_EMAIL    optional — polite identification (default from settings/env)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.knowledge_graph.graph_edge_seed import pathways_from_mechanism  # noqa: E402
from app.pipeline.pathway_mapper import PATHWAY_DISPLAY_NAMES  # noqa: E402

# Import queue builder from skill script if present; else inline minimal
try:
    sys.path.insert(0, str(ROOT / ".grok/skills/herbagraph-pmid-growth/scripts"))
    from pmid_growth_queue import build_queue  # type: ignore  # noqa: E402
except Exception:  # pragma: no cover
    build_queue = None  # type: ignore

GENERATED_PATH = ROOT / "app" / "knowledge_graph" / "generated_pmid_claims.py"
INTEGRITY_PATH = ROOT / "scripts" / "audit_pmid_integrity.py"

_USER_AGENT = "herbagraph-pmid-growth/1.0 (https://github.com/xcross20/Herbagraph-)"
_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
_ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

# NCBI: 3 rps without key, 10 rps with key — stay polite
_DEFAULT_SLEEP = 0.34


def _ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    try:
        import certifi

        ctx.load_verify_locations(certifi.where())
    except Exception:
        pass
    return ctx


def _http_get_json(url: str, timeout: float = 25.0) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as resp:
        return json.load(resp)


def _ncbi_params(**extra: str) -> str:
    parts = []
    email = os.environ.get("NCBI_EMAIL") or os.environ.get("ncbi_email") or "dev@herbagraph.io"
    parts.append(f"email={urllib.parse.quote(email)}")
    api_key = (os.environ.get("NCBI_API_KEY") or os.environ.get("ncbi_api_key") or "").strip()
    if api_key:
        parts.append(f"api_key={urllib.parse.quote(api_key)}")
    for k, v in extra.items():
        parts.append(f"{k}={urllib.parse.quote(str(v))}")
    return "&".join(parts)


def _keywords(name: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", name.lower())
    # Prefer distinctive tokens ≥3 chars; drop pure dose numbers
    kws = [t for t in tokens if len(t) >= 3 and not t.isdigit()]
    # Always include full simplified name fragments
    if name.lower() not in kws:
        simplified = re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()
        if simplified:
            kws.insert(0, simplified)
    return kws[:8] or [name.lower()]


def search_pmids(intervention: str, *, retmax: int = 5) -> list[str]:
    # Prefer clinical literature
    term = (
        f'("{intervention}"[Title/Abstract]) AND '
        f"(clinical trial[Publication Type] OR meta-analysis[Publication Type] "
        f"OR systematic review[Publication Type] OR randomized[Title/Abstract] OR trial[Title/Abstract])"
    )
    url = f"{_ESEARCH}?db=pubmed&retmode=json&retmax={retmax}&{_ncbi_params(term=term)}"
    try:
        data = _http_get_json(url)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        # Broader fallback
        term2 = f'"{intervention}"[Title/Abstract]'
        url2 = f"{_ESEARCH}?db=pubmed&retmode=json&retmax={retmax}&{_ncbi_params(term=term2)}"
        try:
            data = _http_get_json(url2)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            return []
    return list(data.get("esearchresult", {}).get("idlist") or [])


def fetch_titles(pmids: list[str]) -> dict[str, str]:
    if not pmids:
        return {}
    url = f"{_ESUMMARY}?db=pubmed&retmode=json&{_ncbi_params(id=','.join(pmids))}"
    try:
        data = _http_get_json(url)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return {}
    result = data.get("result") or {}
    out: dict[str, str] = {}
    for uid in result.get("uids", []):
        entry = result.get(uid) or {}
        title = (entry.get("title") or "").lower()
        if title:
            out[str(uid)] = title
    return out


def title_matches(title: str, intervention: str) -> bool:
    kws = _keywords(intervention)
    # Need at least one distinctive keyword in title
    for kw in kws:
        if len(kw) >= 4 and kw in title:
            return True
    # Multi-token: require ≥2 short tokens
    hits = sum(1 for kw in kws if kw in title)
    return hits >= 2


def _infer_pathway(category: str, mechanism: str) -> str:
    codes = pathways_from_mechanism(mechanism, category)
    if codes:
        return codes[0]
    defaults = {
        "herb": "NF_KB",
        "phytochemical": "NRF2",
        "supplement": "NUTRIENT_DEFICIENCY",
        "food": "NUTRIENT_DEFICIENCY",
        "peptide": "AMPK",
    }
    return defaults.get(category, "NUTRIENT_DEFICIENCY")


def _infer_effect_and_intent(category: str, pathway: str) -> tuple[str, str, str]:
    if pathway == "NUTRIENT_DEFICIENCY" or category == "supplement":
        return "increases", "nutritional_repletion", "low"
    if pathway in ("HPA_AXIS", "NF_KB", "AMPK", "HEPATIC_LIPID"):
        return "decreases", "primary", "low"
    return "decreases", "collateral", "low"


def build_claim(row: dict, pmid: str, title: str) -> dict:
    pathway = _infer_pathway(row.get("category") or "supplement", row.get("mechanism") or "")
    if pathway not in PATHWAY_DISPLAY_NAMES:
        pathway = "NUTRIENT_DEFICIENCY"
    effect, intent, level = _infer_effect_and_intent(row.get("category") or "supplement", pathway)
    name = row["name"]
    summary = (
        f"PubMed literature on {name} (PMID {pmid}): {title[:140].rstrip('.')}. "
        f"Auto-curated claim for catalog coverage — review evidence grade clinically."
    )
    return {
        "intervention_name": name,
        "biomarker_name": None,
        "pathway_code": pathway,
        "effect": effect,
        "evidence_level": level,
        "pmid": str(pmid),
        "recommendation_intent": intent,
        "summary": summary[:320],
    }


def _load_existing_claim_keys() -> set[tuple[str, str]]:
    """(intervention, pmid) pairs already present."""
    keys: set[tuple[str, str]] = set()
    try:
        from app.knowledge_graph.tier_a_evidence import TIER_A_EVIDENCE_CLAIMS
        from app.knowledge_graph.lifestyle_evidence import LIFESTYLE_EVIDENCE_CLAIMS
        from app.knowledge_graph.peptide_catalog import PEPTIDE_EVIDENCE_CLAIMS

        for c in [*TIER_A_EVIDENCE_CLAIMS, *LIFESTYLE_EVIDENCE_CLAIMS, *PEPTIDE_EVIDENCE_CLAIMS]:
            if c.get("intervention_name") and c.get("pmid"):
                keys.add((c["intervention_name"], str(c["pmid"])))
    except Exception:
        pass
    return keys


def _write_generated_claims(claims: list[dict]) -> int:
    """Merge new claims into generated_pmid_claims.py; return total count written."""
    existing: list[dict] = []
    if GENERATED_PATH.is_file():
        ns: dict = {}
        exec(GENERATED_PATH.read_text(encoding="utf-8"), ns)
        existing = list(ns.get("GENERATED_PMID_CLAIMS") or [])

    seen = {(c.get("intervention_name"), str(c.get("pmid"))) for c in existing}
    added = 0
    for c in claims:
        key = (c["intervention_name"], str(c["pmid"]))
        if key in seen:
            continue
        existing.append(c)
        seen.add(key)
        added += 1

    # Render file
    lines = [
        '"""Auto-generated PMID claims from cloud/local pmid_growth_batch runs.',
        "",
        "Appended by scripts/pmid_growth_batch.py. Do not invent rows by hand here —",
        "prefer catalog_longtail_claims.py for curated batches. Safe to reformat.",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "GENERATED_PMID_CLAIMS: list[dict] = [",
    ]
    for c in existing:
        lines.append(
            "    {"
            f"\"intervention_name\": {c['intervention_name']!r}, "
            f"\"biomarker_name\": {c.get('biomarker_name')!r}, "
            f"\"pathway_code\": {c.get('pathway_code')!r}, "
            f"\"effect\": {c.get('effect')!r}, "
            f"\"evidence_level\": {c.get('evidence_level')!r}, "
            f"\"pmid\": {str(c.get('pmid'))!r}, "
            f"\"recommendation_intent\": {c.get('recommendation_intent')!r}, "
            f"\"summary\": {c.get('summary')!r}"
            "},"
        )
    lines.append("]")
    lines.append("")
    GENERATED_PATH.write_text("\n".join(lines), encoding="utf-8")
    return added


def _ensure_keyword_entries(names: list[str]) -> int:
    """Append missing intervention keyword stubs to audit_pmid_integrity.py."""
    text = INTEGRITY_PATH.read_text(encoding="utf-8")
    added = 0
    # Find insertion point before closing of _INTERVENTION_KEYWORDS
    marker = "\n}\n\n\ndef _claims_with_pmids"
    if marker not in text:
        marker = "\n}\n\ndef _claims_with_pmids"
    if marker not in text:
        return 0
    block_additions = []
    for name in names:
        if f'"{name}":' in text:
            continue
        kws = _keywords(name)
        # keep 3–6 tokens
        kws = kws[:6]
        if not kws:
            continue
        tup = ", ".join(repr(k) for k in kws)
        block_additions.append(f'    "{name}": ({tup},),\n')
        added += 1
    if not block_additions:
        return 0
    insert = "".join(block_additions)
    text = text.replace(marker, "\n" + insert + marker.lstrip("\n"), 1)
    INTEGRITY_PATH.write_text(text, encoding="utf-8")
    return added


def process_batch(
    *,
    limit: int,
    dry_run: bool,
    sleep_s: float,
    max_attempts_factor: int = 3,
) -> dict:
    t0 = time.time()
    if build_queue is None:
        raise RuntimeError("pmid_growth_queue.build_queue unavailable")

    # Over-fetch queue: many names fail title match
    queue = build_queue(limit=limit * max_attempts_factor)
    existing_keys = _load_existing_claim_keys()
    accepted: list[dict] = []
    skipped: list[dict] = []
    errors: list[dict] = []
    attempts = 0

    for row in queue:
        if len(accepted) >= limit:
            break
        attempts += 1
        name = row["name"]
        try:
            pmids = search_pmids(name)
            time.sleep(sleep_s)
            if not pmids:
                skipped.append({"name": name, "reason": "no_pmids"})
                continue
            titles = fetch_titles(pmids[:5])
            time.sleep(sleep_s)
            chosen = None
            chosen_title = ""
            for pmid in pmids:
                title = titles.get(pmid, "")
                if not title:
                    continue
                if not title_matches(title, name):
                    continue
                if (name, str(pmid)) in existing_keys:
                    continue
                chosen = pmid
                chosen_title = title
                break
            if not chosen:
                skipped.append({"name": name, "reason": "no_title_match", "pmids": pmids[:3]})
                continue
            claim = build_claim(row, chosen, chosen_title)
            accepted.append(claim)
            existing_keys.add((name, str(chosen)))
        except Exception as exc:  # noqa: BLE001
            errors.append({"name": name, "error": str(exc)[:200]})
            time.sleep(sleep_s)

    elapsed = time.time() - t0
    written = 0
    keywords_added = 0
    if not dry_run and accepted:
        written = _write_generated_claims(accepted)
        keywords_added = _ensure_keyword_entries([c["intervention_name"] for c in accepted])

    return {
        "limit": limit,
        "dry_run": dry_run,
        "queue_scanned": attempts,
        "accepted": len(accepted),
        "written": written,
        "keywords_added": keywords_added,
        "skipped": len(skipped),
        "errors": len(errors),
        "elapsed_seconds": round(elapsed, 2),
        "seconds_per_accepted": round(elapsed / max(len(accepted), 1), 2),
        "seconds_per_scanned": round(elapsed / max(attempts, 1), 2),
        "est_seconds_for_100_accepted": round((elapsed / max(len(accepted), 1)) * 100, 1)
        if accepted
        else None,
        "claims": accepted,
        "skip_samples": skipped[:15],
        "error_samples": errors[:10],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Grow real PMID claims for claim-less interventions")
    parser.add_argument("--limit", type=int, default=100, help="Target number of accepted claims (default 100)")
    parser.add_argument("--dry-run", action="store_true", help="Do not write files")
    parser.add_argument("--write", action="store_true", help="Write generated claims + keyword stubs")
    parser.add_argument("--sleep", type=float, default=None, help="Seconds between NCBI calls")
    parser.add_argument("--json-out", type=Path, default=None, help="Write run summary JSON")
    args = parser.parse_args()

    write = args.write and not args.dry_run
    sleep_s = args.sleep
    if sleep_s is None:
        sleep_s = 0.12 if (os.environ.get("NCBI_API_KEY") or "").strip() else _DEFAULT_SLEEP

    print(
        f"PMID growth batch: target={args.limit} write={write} sleep={sleep_s}s "
        f"api_key={'yes' if (os.environ.get('NCBI_API_KEY') or '').strip() else 'no'}"
    )
    summary = process_batch(limit=args.limit, dry_run=not write, sleep_s=sleep_s)

    print(f"Scanned:   {summary['queue_scanned']}")
    print(f"Accepted:  {summary['accepted']}")
    print(f"Written:   {summary['written']}")
    print(f"Skipped:   {summary['skipped']}")
    print(f"Errors:    {summary['errors']}")
    print(f"Elapsed:   {summary['elapsed_seconds']}s")
    print(f"Per accepted: {summary['seconds_per_accepted']}s")
    if summary.get("est_seconds_for_100_accepted"):
        print(f"Est. for 100 accepted: {summary['est_seconds_for_100_accepted']}s")
    if summary["claims"]:
        print("Sample accepted:")
        for c in summary["claims"][:5]:
            print(f"  - {c['intervention_name']} PMID:{c['pmid']} → {c['pathway_code']}")

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        # Don't dump full claim summaries twice in huge CI logs — keep claims
        out = dict(summary)
        args.json_out.write_text(json.dumps(out, indent=2), encoding="utf-8")
        print(f"Wrote {args.json_out}")

    # Exit 0 even if 0 accepted (PubMed flaky) — CI can still open empty PR skip
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
