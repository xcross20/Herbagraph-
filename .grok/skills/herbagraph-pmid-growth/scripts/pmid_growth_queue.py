#!/usr/bin/env python3
"""List catalog interventions that still lack any PMID evidence claim.

Usage:
  python3 .grok/skills/herbagraph-pmid-growth/scripts/pmid_growth_queue.py
  python3 .grok/skills/herbagraph-pmid-growth/scripts/pmid_growth_queue.py --limit 25 --json
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


def _claimed_names() -> set[str]:
    names: set[str] = set()
    for claim in [*TIER_A_EVIDENCE_CLAIMS, *LIFESTYLE_EVIDENCE_CLAIMS, *PEPTIDE_EVIDENCE_CLAIMS, *EVIDENCE_CLAIMS]:
        name = claim.get("intervention_name")
        if name:
            names.add(name)
    return names


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


def build_queue(limit: int | None = None) -> list[dict]:
    claimed = _claimed_names()
    missing = [e for e in _catalog_entries() if e["name"] not in claimed]
    missing.sort(
        key=lambda e: (
            _CATEGORY_PRIORITY.get(str(e["category"]), 9),
            0 if e["source"] == "tier_a" else 1,
            e["name"],
        )
    )
    if limit is not None:
        missing = missing[:limit]
    return missing


def main() -> int:
    parser = argparse.ArgumentParser(description="Queue claim-less interventions for PMID growth")
    parser.add_argument("--limit", type=int, default=25, help="Max rows to print (default 25)")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--all", action="store_true", help="Print full queue (ignore default limit display)")
    args = parser.parse_args()

    claimed = _claimed_names()
    catalog = _catalog_entries()
    full = build_queue(limit=None)
    batch = full if args.all else full[: args.limit]

    if args.json:
        print(
            json.dumps(
                {
                    "catalog_interventions": len(catalog),
                    "with_claims": len(claimed),
                    "missing_claims": len(full),
                    "queue": batch,
                },
                indent=2,
            )
        )
        return 0

    by_cat = Counter(e["category"] for e in full)
    print(f"Catalog interventions: {len(catalog)}")
    print(f"With ≥1 claim:         {len(claimed)}")
    print(f"Missing claims:        {len(full)}")
    print("Missing by category:   " + ", ".join(f"{k}={v}" for k, v in by_cat.most_common()))
    print()
    print(f"Next batch (limit={len(batch)}):")
    for i, row in enumerate(batch, 1):
        print(f"  {i:2}. [{row['category']:14}] {row['name']}")
        if row["mechanism"]:
            print(f"      mechanism: {row['mechanism'][:100]}")
    print()
    print("Process with: /herbagraph-pmid-growth")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
