"""Build intervention maps from test-type routing, pathways, and biomarker-direct claims."""

from __future__ import annotations

from app.knowledge_graph.food_seed_data import COMPOUND_TO_FOOD_SOURCES
from app.knowledge_graph.seed_data import EVIDENCE_CLAIMS
from app.knowledge_graph.tier_a_evidence import TIER_A_EVIDENCE_CLAIMS
from app.knowledge_graph.peptide_catalog import PEPTIDE_EVIDENCE_CLAIMS
from app.models.enums import RecommendationIntent, RecommendationTree
from app.pipeline.test_type_router import RecommendationRoutingContext
from app.schemas.pipeline import NormalizedLabResult, PathwayActivation

_INTENT_RANK = {
    RecommendationIntent.PRIMARY.value: 0,
    RecommendationIntent.NUTRITIONAL_REPLETION.value: 1,
    RecommendationIntent.COLLATERAL.value: 2,
    RecommendationIntent.CONTEXT_ONLY.value: 3,
}
_EVIDENCE_LEVEL_RANK = {"high": 0, "moderate": 1, "low": 2, "preclinical": 3}
_MAX_PER_ROUTE = 12

# Trees that should prefer biomarker-direct claims over generic pathway neighbors.
_BIOMARKER_DIRECT_TREES = frozenset({
    RecommendationTree.ETIOLOGICAL,
    RecommendationTree.CELIAC,
    RecommendationTree.ALLERGY,
    RecommendationTree.CULTURE,
    RecommendationTree.EXPOSURE,
    RecommendationTree.NUTRITIONAL_REPLETION,
    RecommendationTree.PGX_CONTEXT,
})


def _all_evidence_claims() -> list[dict]:
    return [*EVIDENCE_CLAIMS, *PEPTIDE_EVIDENCE_CLAIMS]


def _abnormal_biomarker_names(labs: list[NormalizedLabResult]) -> set[str]:
    return {
        lab.biomarker_name
        for lab in labs
        if lab.status.value in ("critical_low", "low", "high", "critical_high")
    }


def _claims_for_biomarkers(biomarker_names: set[str], *, trees: list[RecommendationTree]) -> list[dict]:
    claims = []
    for claim in _all_evidence_claims():
        biomarker = claim.get("biomarker_name")
        if biomarker and biomarker in biomarker_names:
            intent = claim.get("recommendation_intent", RecommendationIntent.PRIMARY.value)
            if RecommendationTree.PGX_CONTEXT in trees and intent == RecommendationIntent.CONTEXT_ONLY.value:
                claims.append(claim)
            elif intent != RecommendationIntent.CONTEXT_ONLY.value:
                claims.append(claim)
            elif RecommendationTree.EXPOSURE in trees:
                claims.append(claim)
    return claims


def _claims_for_pathways(pathway_codes: set[str]) -> list[dict]:
    return [c for c in _all_evidence_claims() if c.get("pathway_code") in pathway_codes]


def _rank_claim(claim: dict, primary_tree: RecommendationTree | None) -> tuple[int, int, int]:
    intent = claim.get("recommendation_intent", RecommendationIntent.PRIMARY.value)
    intent_rank = _INTENT_RANK.get(intent, 9)
    # Boost primary-tree biomarker-direct claims
    tree_boost = 0
    if primary_tree == RecommendationTree.ETIOLOGICAL and claim.get("pathway_code", "").startswith("GASTRIC"):
        tree_boost = -1
    if primary_tree == RecommendationTree.CELIAC and claim.get("pathway_code") == "FOOD_ANTIGEN_EXPOSURE":
        tree_boost = -1
    level = _EVIDENCE_LEVEL_RANK.get(claim.get("evidence_level", "low"), 9)
    has_food = 0 if claim["intervention_name"] in COMPOUND_TO_FOOD_SOURCES else 1
    return (intent_rank + tree_boost, level, has_food)


def build_interventions_for_routing(
    routing: RecommendationRoutingContext,
    pathway_activations: list[PathwayActivation],
    normalized_labs: list[NormalizedLabResult],
) -> dict[str, list[str]]:
    """Return pathway_code -> ranked intervention names for evidence retrieval."""
    abnormal = _abnormal_biomarker_names(normalized_labs)
    pathway_codes = {a.pathway_code for a in pathway_activations}

    biomarker_claims = _claims_for_biomarkers(abnormal, trees=routing.trees)
    pathway_claims = _claims_for_pathways(pathway_codes)

    use_biomarker_first = any(t in _BIOMARKER_DIRECT_TREES for t in routing.trees)
    claims = biomarker_claims + pathway_claims if use_biomarker_first else pathway_claims + biomarker_claims

    # PGx tree: context-only interventions, no broad pathway sweep
    if routing.primary_tree == RecommendationTree.PGX_CONTEXT:
        claims = [c for c in biomarker_claims if c.get("recommendation_intent") == RecommendationIntent.CONTEXT_ONLY.value]

    ranked_claims = sorted(claims, key=lambda c: _rank_claim(c, routing.primary_tree))

    result: dict[str, list[str]] = {}
    for claim in ranked_claims:
        code = claim.get("pathway_code")
        if not code:
            continue
        names = result.setdefault(code, [])
        name = claim["intervention_name"]
        if name not in names:
            names.append(name)
        if len(names) >= _MAX_PER_ROUTE:
            continue

    # Ensure activated pathways without claims still appear (empty list filtered later)
    for activation in pathway_activations:
        result.setdefault(activation.pathway_code, [])

    return result


def build_pathway_intervention_map(
    routing: RecommendationRoutingContext | None = None,
    pathway_activations: list[PathwayActivation] | None = None,
    normalized_labs: list[NormalizedLabResult] | None = None,
) -> dict[str, list[str]]:
    """Pathway code -> intervention names (legacy API with optional routing context)."""
    if routing and pathway_activations is not None and normalized_labs is not None:
        return build_interventions_for_routing(routing, pathway_activations, normalized_labs)

    # Fallback: pathway-only map from seeded claims (tests / legacy callers).
    grouped: dict[str, list[str]] = {}
    for claim in _all_evidence_claims():
        code = claim.get("pathway_code")
        if not code:
            continue
        grouped.setdefault(code, [])
        name = claim["intervention_name"]
        if name not in grouped[code]:
            grouped[code].append(name)
    return grouped


def build_intervention_pathway_map(
    routing: RecommendationRoutingContext | None = None,
    pathway_activations: list[PathwayActivation] | None = None,
    normalized_labs: list[NormalizedLabResult] | None = None,
) -> dict[str, list[str]]:
    """Invert pathway map: intervention_name -> [pathway_code, ...]."""
    mapping: dict[str, list[str]] = {}
    for pathway_code, names in build_pathway_intervention_map(routing, pathway_activations, normalized_labs).items():
        for name in names:
            mapping.setdefault(name, []).append(pathway_code)
    return mapping


def intent_for_intervention(
    intervention_name: str,
    abnormal_biomarkers: set[str],
) -> str:
    """Best recommendation_intent for narrative labeling."""
    matching = [
        c for c in TIER_A_EVIDENCE_CLAIMS
        if c["intervention_name"] == intervention_name
        and (c.get("biomarker_name") in abnormal_biomarkers or c.get("biomarker_name") is None)
    ]
    if not matching:
        return RecommendationIntent.COLLATERAL.value
    best = min(matching, key=lambda c: _INTENT_RANK.get(c.get("recommendation_intent", "collateral"), 9))
    return best.get("recommendation_intent", RecommendationIntent.COLLATERAL.value)