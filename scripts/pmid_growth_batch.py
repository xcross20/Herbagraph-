#!/usr/bin/env python3
"""Cloud/local batch: grow real PMID claims for catalog interventions.

Uses NCBI E-utilities only — never invents PMIDs. A claim is written only when a
PubMed title matches intervention keywords.

Examples:
  # Timed dry-run of 100 (no file write)
  python3 scripts/pmid_growth_batch.py --limit 100 --dry-run

  # Write up to 150 validated claims (daily cloud target)
  python3 scripts/pmid_growth_batch.py --limit 150 --write

  # Hour marathon (~thousands with hybrid mode + API key)
  python3 scripts/pmid_growth_batch.py --max-seconds 3600 --limit 5000 \\
      --mode hybrid --write --checkpoint-every 50 \\
      --json-out ops/pmid_growth_last_run.json

  # JSON summary for CI
  python3 scripts/pmid_growth_batch.py --limit 100 --write --json-out ops/pmid_growth_last_run.json

Env:
  NCBI_API_KEY  optional — higher rate limit (~10 rps vs ~3)
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


def search_pmids(intervention: str, *, retmax: int = 5, offset: int = 0) -> list[str]:
    """Search PubMed; offset paginates for depth mode (extra PMIDs)."""
    # Prefer clinical literature
    term = (
        f'("{intervention}"[Title/Abstract]) AND '
        f"(clinical trial[Publication Type] OR meta-analysis[Publication Type] "
        f"OR systematic review[Publication Type] OR randomized[Title/Abstract] OR trial[Title/Abstract])"
    )
    url = (
        f"{_ESEARCH}?db=pubmed&retmode=json&retmax={retmax}&retstart={offset}"
        f"&{_ncbi_params(term=term)}"
    )
    try:
        data = _http_get_json(url)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        # Broader fallback
        term2 = f'"{intervention}"[Title/Abstract]'
        url2 = (
            f"{_ESEARCH}?db=pubmed&retmode=json&retmax={retmax}&retstart={offset}"
            f"&{_ncbi_params(term=term2)}"
        )
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
    max_seconds: float | None = None,
    mode: str = "claimless",
    min_claims: int = 3,
    checkpoint_every: int = 0,
    max_attempts_factor: int = 4,
) -> dict:
    """Grow claims until limit accepted or max_seconds wall clock (whichever first)."""
    t0 = time.time()
    if build_queue is None:
        raise RuntimeError("pmid_growth_queue.build_queue unavailable")

    # Over-fetch queue: many names fail title match; marathon needs headroom
    queue_cap = max(limit * max_attempts_factor, limit + 500)
    if max_seconds and max_seconds >= 1800:
        # Hour runs: pull the full hybrid catalog so we do not starve mid-run
        queue_cap = max(queue_cap, 8000)
    queue = build_queue(limit=queue_cap, mode=mode, min_claims=min_claims)
    existing_keys = _load_existing_claim_keys()
    accepted: list[dict] = []
    skipped: list[dict] = []
    errors: list[dict] = []
    attempts = 0
    checkpoints = 0
    written_total = 0
    keywords_total = 0
    stop_reason = "queue_exhausted"
    last_checkpoint_at = 0

    def _maybe_checkpoint(force: bool = False) -> None:
        nonlocal checkpoints, written_total, keywords_total, last_checkpoint_at
        if dry_run or not accepted:
            return
        if not force and (checkpoint_every <= 0 or len(accepted) - last_checkpoint_at < checkpoint_every):
            return
        # Only flush claims not yet written (slice from last checkpoint)
        chunk = accepted[last_checkpoint_at:]
        if not chunk:
            return
        written_total += _write_generated_claims(chunk)
        keywords_total += _ensure_keyword_entries([c["intervention_name"] for c in chunk])
        last_checkpoint_at = len(accepted)
        checkpoints += 1
        print(
            f"  checkpoint #{checkpoints}: accepted={len(accepted)} "
            f"elapsed={time.time() - t0:.0f}s",
            flush=True,
        )

    for row in queue:
        if len(accepted) >= limit:
            stop_reason = "limit_reached"
            break
        if max_seconds is not None and (time.time() - t0) >= max_seconds:
            stop_reason = "max_seconds"
            break

        attempts += 1
        name = row["name"]
        queue_mode = row.get("queue_mode") or mode
        existing_for_name = int(row.get("existing_claims") or 0)
        # How many new claims to take from this intervention this pass.
        # Marathon/hybrid uses min_claims>1 so claimless rows also fill multiple PMIDs.
        if min_claims > 1 or queue_mode == "depth":
            per_name_cap = max(1, min_claims - existing_for_name)
            retmax = min(20, max(8, per_name_cap * 5))
            offset = 0 if existing_for_name == 0 else min(existing_for_name * 3, 40)
        else:
            per_name_cap = 1
            retmax = 5
            offset = 0
        try:
            pmids = search_pmids(name, retmax=retmax, offset=offset)
            time.sleep(sleep_s)
            if not pmids:
                skipped.append({"name": name, "reason": "no_pmids", "mode": queue_mode})
                continue
            titles = fetch_titles(pmids[:retmax])
            time.sleep(sleep_s)
            took = 0
            for pmid in pmids:
                if len(accepted) >= limit:
                    break
                if max_seconds is not None and (time.time() - t0) >= max_seconds:
                    break
                if took >= per_name_cap:
                    break
                title = titles.get(pmid, "")
                if not title:
                    continue
                if not title_matches(title, name):
                    continue
                if (name, str(pmid)) in existing_keys:
                    continue
                claim = build_claim(row, pmid, title)
                accepted.append(claim)
                existing_keys.add((name, str(pmid)))
                took += 1
                _maybe_checkpoint(force=False)
            if took == 0:
                skipped.append(
                    {
                        "name": name,
                        "reason": "no_title_match",
                        "pmids": pmids[:3],
                        "mode": queue_mode,
                    }
                )
        except Exception as exc:  # noqa: BLE001
            errors.append({"name": name, "error": str(exc)[:200]})
            time.sleep(sleep_s)

    # Final flush of any un-checkpointed claims
    if not dry_run and accepted:
        if checkpoint_every > 0:
            _maybe_checkpoint(force=True)
        else:
            written_total = _write_generated_claims(accepted)
            keywords_total = _ensure_keyword_entries([c["intervention_name"] for c in accepted])

    elapsed = time.time() - t0
    return {
        "limit": limit,
        "max_seconds": max_seconds,
        "mode": mode,
        "min_claims": min_claims,
        "dry_run": dry_run,
        "stop_reason": stop_reason,
        "queue_size": len(queue),
        "queue_scanned": attempts,
        "accepted": len(accepted),
        "written": written_total,
        "keywords_added": keywords_total,
        "checkpoints": checkpoints,
        "skipped": len(skipped),
        "errors": len(errors),
        "elapsed_seconds": round(elapsed, 2),
        "seconds_per_accepted": round(elapsed / max(len(accepted), 1), 2),
        "seconds_per_scanned": round(elapsed / max(attempts, 1), 2),
        "est_seconds_for_100_accepted": round((elapsed / max(len(accepted), 1)) * 100, 1)
        if accepted
        else None,
        "est_accepted_per_hour": round((len(accepted) / max(elapsed, 0.001)) * 3600, 0)
        if accepted
        else None,
        "api_key": bool((os.environ.get("NCBI_API_KEY") or "").strip()),
        "claims": accepted,
        "skip_samples": skipped[:15],
        "error_samples": errors[:10],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Grow real PMID claims (daily batch or hour marathon)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Max accepted claims this run (default 100; marathon often 3000–5000)",
    )
    parser.add_argument(
        "--max-seconds",
        type=float,
        default=None,
        help="Stop after this many wall-clock seconds (e.g. 3600 for one hour)",
    )
    parser.add_argument(
        "--mode",
        choices=("claimless", "depth", "hybrid"),
        default="claimless",
        help="Queue mode: claimless | depth | hybrid (default claimless; marathon → hybrid)",
    )
    parser.add_argument(
        "--min-claims",
        type=int,
        default=3,
        help="Depth/hybrid: keep adding PMIDs until intervention has this many (default 3)",
    )
    parser.add_argument(
        "--checkpoint-every",
        type=int,
        default=0,
        help="Write claims to disk every N accepts (recommended 50 for hour runs)",
    )
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
        f"PMID growth batch: target={args.limit} max_seconds={args.max_seconds} "
        f"mode={args.mode} min_claims={args.min_claims} write={write} "
        f"checkpoint_every={args.checkpoint_every} sleep={sleep_s}s "
        f"api_key={'yes' if (os.environ.get('NCBI_API_KEY') or '').strip() else 'no'}",
        flush=True,
    )
    summary = process_batch(
        limit=args.limit,
        dry_run=not write,
        sleep_s=sleep_s,
        max_seconds=args.max_seconds,
        mode=args.mode,
        min_claims=args.min_claims,
        checkpoint_every=args.checkpoint_every if write else 0,
    )

    print(f"Stop reason: {summary['stop_reason']}")
    print(f"Scanned:   {summary['queue_scanned']}")
    print(f"Accepted:  {summary['accepted']}")
    print(f"Written:   {summary['written']}")
    print(f"Skipped:   {summary['skipped']}")
    print(f"Errors:    {summary['errors']}")
    print(f"Elapsed:   {summary['elapsed_seconds']}s")
    print(f"Per accepted: {summary['seconds_per_accepted']}s")
    if summary.get("est_accepted_per_hour") is not None:
        print(f"Est. rate: ~{int(summary['est_accepted_per_hour'])} accepted/hour")
    if summary.get("est_seconds_for_100_accepted"):
        print(f"Est. for 100 accepted: {summary['est_seconds_for_100_accepted']}s")
    if summary["claims"]:
        print("Sample accepted:")
        for c in summary["claims"][:5]:
            print(f"  - {c['intervention_name']} PMID:{c['pmid']} → {c['pathway_code']}")

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        out = dict(summary)
        # Cap claims in JSON for huge marathon runs (keep samples)
        if len(out.get("claims") or []) > 200:
            out["claims_truncated"] = True
            out["claims_full_count"] = len(out["claims"])
            out["claims"] = out["claims"][:200]
        args.json_out.write_text(json.dumps(out, indent=2), encoding="utf-8")
        print(f"Wrote {args.json_out}")

    # Exit 0 even if 0 accepted (PubMed flaky) — CI can still open empty PR skip
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
