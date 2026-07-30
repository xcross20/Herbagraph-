#!/usr/bin/env python3
"""Audit pathway → intervention evidence coverage (primary + nutritional_repletion)."""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.knowledge_graph.peptide_catalog import PEPTIDE_EVIDENCE_CLAIMS
from app.knowledge_graph.tier_a_evidence import TIER_A_EVIDENCE_CLAIMS
from app.pipeline.pathway_mapper import PATHWAY_DISPLAY_NAMES

ROUTABLE_INTENTS = frozenset({"primary", "nutritional_repletion"})

# User-facing and high-traffic clinical pathways (see biological_systems + etiological trees).
PRIORITY_PATHWAYS: tuple[str, ...] = (
    "NF_KB",
    "IL6_JAK_STAT3",
    "AMPK",
    "INSULIN_PI3K_AKT",
    "HEPATIC_LIPID",
    "ONE_CARBON_METHYLATION",
    "IRON_HEPCIDIN",
    "VITAMIN_D_RECEPTOR",
    "NUTRIENT_DEFICIENCY",
    "THYROID_HPT",
    "HPA_AXIS",
    "NRF2",
    "GASTRIC_COLONIZATION",
    "FOOD_ANTIGEN_EXPOSURE",
    "IGE_SENSITIZATION",
    "AUTOIMMUNE_TARGETING",
    "MITOCHONDRIAL_NAD",
    "GI_MUCOSAL_BARRIER",
    "PATHOGEN_BURDEN",
    "GLP1_INCRETINS",
    "URINARY_PATHOGEN",
    "BIOFILM_ADHESION",
    "RESPIRATORY_PATHOGEN",
    "HEPATOTROPIC_VIRAL",
    "PURINE_URIC_ACID",
    "MTOR_AUTOPHAGY",
    "RENAL_FILTRATION",
    "DRUG_METABOLISM_VARIANT",
)

# Raised as catalog density grows (was 3).
MIN_PRIORITY_CLAIMS = 5


def _routable_claims() -> list[dict]:
    claims: list[dict] = []
    for claim in [*TIER_A_EVIDENCE_CLAIMS, *PEPTIDE_EVIDENCE_CLAIMS]:
        intent = claim.get("recommendation_intent", "primary")
        pathway = claim.get("pathway_code")
        if intent in ROUTABLE_INTENTS:
            claims.append(claim)
        elif intent == "context_only" and pathway == "DRUG_METABOLISM_VARIANT":
            claims.append(claim)
    return claims


def main() -> int:
    claims = _routable_claims()
    by_pathway: Counter[str] = Counter()
    for claim in claims:
        code = claim.get("pathway_code")
        if code:
            by_pathway[code] += 1

    all_codes = sorted(PATHWAY_DISPLAY_NAMES)
    zero_routable = [code for code in all_codes if by_pathway[code] == 0]

    print(f"Routable catalog claims: {len(claims)}")
    print(f"Pathways with zero routable claims: {len(zero_routable)}")
    for code in zero_routable:
        print(f"  - {code}: {PATHWAY_DISPLAY_NAMES[code]}")

    print(f"\nPriority pathway routable claim counts (min {MIN_PRIORITY_CLAIMS}):")
    shortfalls: list[tuple[str, int]] = []
    for code in PRIORITY_PATHWAYS:
        count = by_pathway[code]
        label = PATHWAY_DISPLAY_NAMES.get(code, code)
        status = "ok" if count >= MIN_PRIORITY_CLAIMS else "SHORT"
        print(f"  [{status}] {code}: {count} ({label})")
        if count < MIN_PRIORITY_CLAIMS:
            shortfalls.append((code, count))

    if shortfalls:
        print(f"\nFAIL: {len(shortfalls)} priority pathway(s) have < {MIN_PRIORITY_CLAIMS} routable claims.")
        return 1

    print(
        f"\nAll {len(PRIORITY_PATHWAYS)} priority pathways have "
        f">= {MIN_PRIORITY_CLAIMS} routable claims."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
