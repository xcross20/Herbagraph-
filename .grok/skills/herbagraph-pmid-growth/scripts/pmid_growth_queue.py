#!/usr/bin/env python3
"""Queue catalog interventions for PMID growth.

Modes:
  claimless — interventions with zero PMID claims (default, highest priority)
  depth     — interventions that already have claims but fewer than --min-claims
  hybrid    — claimless first, then depth (for hour-long marathon runs)

Usage:
  python3 .grok/skills/herbagraph-pmid-growth/scripts/pmid_growth_queue.py
  python3 .grok/skills/herbagraph-pmid-growth/scripts/pmid_growth_queue.py --limit 25 --json
  python3 .grok/skills/herbagraph-pmid-growth/scripts/pmid_growth_queue.py --mode hybrid --limit 5000
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

# .../herbagraph/.grok/skills/herbagraph-pmid-growth/scripts/this_file.py → repo root is parents[4]
ROOT = Path(__file__).resolve().parents[4]
if not (ROOT / "app").is_dir():
    # Fallback if skill is nested differently
    ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from app.knowledge_graph.food_catalog import FOOD_INTERVENTIONS  # noqa: E402
from app.knowledge_graph.herb_catalog import HERB_INTERVENTIONS  # noqa: E402
from app.knowledge_graph.lifestyle_evidence import LIFESTYLE_EVIDENCE_CLAIMS  # noqa: E402
from app.knowledge_graph.lifestyle_methods_catalog import LIFESTYLE_INTERVENTIONS  # noqa: E402
from app.knowledge_graph.peptide_catalog import PEPTIDE_EVIDENCE_CLAIMS, PEPTIDE_INTERVENTIONS  # noqa: E402
from app.knowledge_graph.phytochemical_catalog import PHYTOCHEMICAL_COMPOUNDS  # noqa: E402
from app.knowledge_graph.seed_data import EVIDENCE_CLAIMS, INTERVENTIONS  # noqa: E402
from app.knowledge_graph.supplement_catalog import SUPPLEMENT_INTERVENTIONS  # noqa: E402
from app.knowledge_graph.tier_a_catalog import TIER_A_INTERVENTIONS  # noqa: E402
from app.knowledge_graph.tier_a_evidence import TIER_A_EVIDENCE_CLAIMS  # noqa: E402

# Prefer high-value categories when ranking the queue
_CATEGORY_PRIORITY = {
    "supplement": 0,
    "herb": 1,
    "phytochemical": 2,
    "food": 3,
    "peptide": 4,
    "exercise": 5,
    "sleep": 5,
    "stress_reduction": 5,
    "behavior": 5,
    "medication": 6,
}


def _all_claims() -> list[dict]:
    return [
        *TIER_A_EVIDENCE_CLAIMS,
        *LIFESTYLE_EVIDENCE_CLAIMS,
        *PEPTIDE_EVIDENCE_CLAIMS,
        *EVIDENCE_CLAIMS,
    ]


def _claimed_names() -> set[str]:
    names: set[str] = set()
    for claim in _all_claims():
        name = claim.get("intervention_name")
        if name:
            names.add(name)
    return names


def _claim_counts() -> Counter[str]:
    counts: Counter[str] = Counter()
    for claim in _all_claims():
        name = claim.get("intervention_name")
        pmid = claim.get("pmid")
        if name and pmid:
            counts[name] += 1
    return counts


def _catalog_entries() -> list[dict]:
    by_name: dict[str, dict] = {}
    for source, rows in (
        ("tier_a", TIER_A_INTERVENTIONS),
        ("seed_merge", INTERVENTIONS),
        ("herb", HERB_INTERVENTIONS),
        ("supplement", SUPPLEMENT_INTERVENTIONS),
        ("food", FOOD_INTERVENTIONS),
        ("phyto", PHYTOCHEMICAL_COMPOUNDS),
        ("lifestyle", LIFESTYLE_INTERVENTIONS),
        ("peptide", PEPTIDE_INTERVENTIONS),
    ):
        for row in rows:
            name = row.get("name")
            if not name or name in by_name:
                continue
            by_name[name] = {
                "name": name,
                "category": row.get("category") or "supplement",
                "source": source,
                "mechanism": (row.get("mechanism") or "")[:160],
            }
    return list(by_name.values())


def build_queue(
    limit: int | None = None,
    *,
    mode: str = "claimless",
    min_claims: int = 3,
) -> list[dict]:
    """Build a prioritized queue of interventions to search.

    mode:
      claimless — zero PMID claims only
      depth     — has some claims but fewer than min_claims (extra PMIDs)
      hybrid    — claimless first, then depth (marathon)
    """
    mode = (mode or "claimless").strip().lower()
    if mode not in {"claimless", "depth", "hybrid"}:
        raise ValueError(f"Unknown queue mode: {mode}")

    claimed = _claimed_names()
    counts = _claim_counts()
    catalog = _catalog_entries()

    claimless = [e for e in catalog if e["name"] not in claimed]
    claimless.sort(
        key=lambda e: (
            _CATEGORY_PRIORITY.get(str(e["category"]), 9),
            0 if e["source"] == "tier_a" else 1,
            e["name"],
        )
    )

    depth = [
        {
            **e,
            "existing_claims": counts.get(e["name"], 0),
            "queue_mode": "depth",
        }
        for e in catalog
        if 0 < counts.get(e["name"], 0) < min_claims
    ]
    # Fewest claims first, then category priority
    depth.sort(
        key=lambda e: (
            e["existing_claims"],
            _CATEGORY_PRIORITY.get(str(e["category"]), 9),
            e["name"],
        )
    )

    for e in claimless:
        e["existing_claims"] = 0
        e["queue_mode"] = "claimless"

    if mode == "claimless":
        missing = claimless
    elif mode == "depth":
        missing = depth
    else:  # hybrid
        missing = claimless + depth

    if limit is not None:
        missing = missing[:limit]
    return missing


def main() -> int:
    parser = argparse.ArgumentParser(description="Queue interventions for PMID growth")
    parser.add_argument("--limit", type=int, default=25, help="Max rows to print (default 25)")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--all", action="store_true", help="Print full queue (ignore default limit display)")
    parser.add_argument(
        "--mode",
        choices=("claimless", "depth", "hybrid"),
        default="claimless",
        help="claimless | depth | hybrid (default claimless)",
    )
    parser.add_argument(
        "--min-claims",
        type=int,
        default=3,
        help="Depth mode: target minimum PMID claims per intervention (default 3)",
    )
    args = parser.parse_args()

    catalog = _catalog_entries()
    claimed = _claimed_names()
    full = build_queue(limit=None, mode=args.mode, min_claims=args.min_claims)
    batch = full if args.all else full[: args.limit]

    if args.json:
        print(
            json.dumps(
                {
                    "catalog_interventions": len(catalog),
                    "with_claims": len(claimed),
                    "mode": args.mode,
                    "min_claims": args.min_claims,
                    "queue_size": len(full),
                    "queue": batch,
                },
                indent=2,
            )
        )
        return 0

    by_cat = Counter(e["category"] for e in full)
    by_mode = Counter(e.get("queue_mode", args.mode) for e in full)
    print(f"Catalog interventions: {len(catalog)}")
    print(f"With ≥1 claim:         {len(claimed)}")
    print(f"Queue mode:            {args.mode} (min_claims={args.min_claims})")
    print(f"Queue size:            {len(full)}")
    print("By queue_mode:         " + ", ".join(f"{k}={v}" for k, v in by_mode.most_common()))
    print("By category:           " + ", ".join(f"{k}={v}" for k, v in by_cat.most_common()))
    print()
    print(f"Next batch (showing {len(batch)}):")
    for i, row in enumerate(batch, 1):
        tag = row.get("queue_mode", args.mode)
        n = row.get("existing_claims", 0)
        print(f"  {i:2}. [{tag:9}|{row['category']:14}|n={n}] {row['name']}")
        if row.get("mechanism"):
            print(f"      mechanism: {row['mechanism'][:100]}")
    print()
    print("Process with: /herbagraph-pmid-growth  or  scripts/pmid_growth_batch.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
