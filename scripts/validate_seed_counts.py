#!/usr/bin/env python3
"""Validate knowledge-graph seed catalog counts (no database required)."""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.knowledge_graph.food_compound_links import FOOD_COMPOUND_SOURCES
from app.knowledge_graph.food_seed_data import (
    FOOD_COMPOUND_EVIDENCE_CLAIMS,
    FOOD_INTERVENTIONS,
    PHYTOCHEMICAL_COMPOUNDS,
)
from app.knowledge_graph.lifestyle_methods_catalog import LIFESTYLE_INTERVENTIONS
from app.knowledge_graph.peptide_catalog import PEPTIDE_EVIDENCE_CLAIMS, PEPTIDE_INTERVENTIONS
from app.knowledge_graph.seed_data import BIOMARKERS, EVIDENCE_CLAIMS, expected_seeded_intervention_count

LIFESTYLE_CATEGORIES = ("exercise", "sleep", "stress_reduction", "behavior", "medication", "hormone", "environmental")
MIN_FOOD_LINKS = 200
MIN_LIFESTYLE_PER_CATEGORY = 10


def main() -> int:
    expected_interventions = expected_seeded_intervention_count(
        food_interventions=FOOD_INTERVENTIONS,
        phytochemical_compounds=PHYTOCHEMICAL_COMPOUNDS,
        peptide_interventions=PEPTIDE_INTERVENTIONS,
    )
    expected_claims = len(EVIDENCE_CLAIMS) + len(FOOD_COMPOUND_EVIDENCE_CLAIMS) + len(PEPTIDE_EVIDENCE_CLAIMS)

    print(f"Biomarkers: {len(BIOMARKERS)}")
    print(f"Expected interventions (deduped): {expected_interventions}")
    print(f"Expected evidence claims: {expected_claims}")
    print(f"Food-compound links: {len(FOOD_COMPOUND_SOURCES)}")

    failed = False

    if len(FOOD_COMPOUND_SOURCES) < MIN_FOOD_LINKS:
        print(f"FAIL: food-compound links {len(FOOD_COMPOUND_SOURCES)} < {MIN_FOOD_LINKS}")
        failed = True

    by_category = Counter(i["category"] for i in LIFESTYLE_INTERVENTIONS)
    for category in LIFESTYLE_CATEGORIES:
        count = by_category[category]
        if count < MIN_LIFESTYLE_PER_CATEGORY:
            print(f"FAIL: lifestyle {category} has {count} < {MIN_LIFESTYLE_PER_CATEGORY}")
            failed = True

    if failed:
        return 1

    print("Seed catalog counts OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())