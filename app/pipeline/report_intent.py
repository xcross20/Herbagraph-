"""Display intent classification for report presentation."""

from __future__ import annotations

from app.knowledge_graph.lifestyle_evidence import LIFESTYLE_EVIDENCE_CLAIMS
from app.knowledge_graph.seed_data import EVIDENCE_CLAIMS
from app.knowledge_graph.tier_a_evidence import TIER_A_EVIDENCE_CLAIMS
from app.models.enums import (
    DisplayIntent,
    EvidenceLevel,
    EvidenceTier,
    InterventionCategory,
    RecommendationIntent,
)

_INTENT_RANK = {
    RecommendationIntent.PRIMARY.value: 0,
    RecommendationIntent.NUTRITIONAL_REPLETION.value: 1,
    RecommendationIntent.COLLATERAL.value: 2,
    RecommendationIntent.CONTEXT_ONLY.value: 3,
}

REGULATED_CATEGORIES = frozenset({
    InterventionCategory.MEDICATION.value,
    InterventionCategory.PEPTIDE.value,
    InterventionCategory.HORMONE.value,
})

_ALL_CLAIMS = [*EVIDENCE_CLAIMS, *TIER_A_EVIDENCE_CLAIMS, *LIFESTYLE_EVIDENCE_CLAIMS]


def _category_value(category) -> str:
    if hasattr(category, "value"):
        return category.value
    return str(category or "")


def _tier_value(tier) -> str:
    if hasattr(tier, "value"):
        return tier.value
    return str(tier or EvidenceTier.RESEARCH_HYPOTHESIS.value)


def _level_value(level) -> str:
    if hasattr(level, "value"):
        return level.value
    return str(level or EvidenceLevel.LOW.value)


def recommendation_intent_for(
    intervention_name: str,
    abnormal_biomarkers: set[str],
) -> str:
    matching = [
        c
        for c in _ALL_CLAIMS
        if c["intervention_name"] == intervention_name
        and (c.get("biomarker_name") in abnormal_biomarkers or c.get("biomarker_name") is None)
    ]
    if not matching:
        return RecommendationIntent.COLLATERAL.value
    best = min(matching, key=lambda c: _INTENT_RANK.get(c.get("recommendation_intent", "collateral"), 9))
    return best.get("recommendation_intent", RecommendationIntent.COLLATERAL.value)


_LIFESTYLE_CATEGORIES = frozenset({
    InterventionCategory.EXERCISE.value,
    InterventionCategory.SLEEP.value,
    InterventionCategory.STRESS_REDUCTION.value,
    InterventionCategory.BEHAVIOR.value,
    InterventionCategory.ENVIRONMENTAL.value,
})

_DIET_KEYWORDS = (
    "diet",
    "eating",
    "fasting",
    "mediterranean",
    "portfolio",
    "plant-based",
    "dash",
    "time-restricted",
)


def _is_lifestyle_pattern(rec: dict) -> bool:
    category = _category_value(rec.get("category"))
    name = (rec.get("intervention_name") or "").lower()
    if category in _LIFESTYLE_CATEGORIES:
        return True
    return any(kw in name for kw in _DIET_KEYWORDS)


def _direct_abnormal_claims(intervention_name: str, abnormal_biomarkers: set[str]) -> list[dict]:
    return [
        c
        for c in _ALL_CLAIMS
        if c["intervention_name"] == intervention_name and c.get("biomarker_name") in abnormal_biomarkers
    ]


def classify_intervention_intent_label(
    rec: dict,
    abnormal_biomarkers: set[str],
    *,
    display_intent: str | None = None,
) -> str:
    """Rich clinician-facing intent — distinct from evidence tier or display bucket."""
    category = _category_value(rec.get("category"))
    name = rec.get("intervention_name", "")
    intent = display_intent or classify_display_intent(rec, abnormal_biomarkers)
    rec_intent = recommendation_intent_for(name, abnormal_biomarkers)
    has_direct = bool(_direct_abnormal_claims(name, abnormal_biomarkers))

    if intent == DisplayIntent.REGULATED.value or category in REGULATED_CATEGORIES or rec.get("is_regulated"):
        return "Regulated Context Only"

    if _is_lifestyle_pattern(rec):
        return "Lifestyle Foundation"

    if rec_intent == RecommendationIntent.NUTRITIONAL_REPLETION.value:
        if has_direct and {"Iron", "Ferritin"} & abnormal_biomarkers:
            return "Nutritional Repletion / Diagnostic Follow-up"
        return "Nutritional Repletion"

    if display_intent == DisplayIntent.MECHANISTIC.value or (
        _tier_value(rec.get("evidence_tier"))
        in (EvidenceTier.PRECLINICAL.value, EvidenceTier.RESEARCH_HYPOTHESIS.value)
    ):
        return "Supportive Mechanistic Adjunct"

    if rec_intent == RecommendationIntent.PRIMARY.value and has_direct:
        problem_tokens = " ".join(abnormal_biomarkers).lower()
        if any(tok in problem_tokens for tok in ("hba1c", "glucose", "ldl", "triglyceride")):
            return "Primary Metabolic Support"
        if any(tok in problem_tokens for tok in ("iron", "ferritin", "hemoglobin")):
            return "Primary Iron Pathway Support"
        return "Primary"

    if rec_intent == RecommendationIntent.COLLATERAL.value:
        return "Supportive"

    if intent == DisplayIntent.CONTEXT_ONLY.value:
        return "Context Only"

    if rec_intent == RecommendationIntent.PRIMARY.value:
        return "Primary"

    return "Supportive"


def classify_display_intent(rec: dict, abnormal_biomarkers: set[str]) -> str:
    category = _category_value(rec.get("category"))
    if rec.get("is_regulated") or category in REGULATED_CATEGORIES:
        return DisplayIntent.REGULATED.value

    intent = recommendation_intent_for(rec.get("intervention_name", ""), abnormal_biomarkers)
    if intent == RecommendationIntent.CONTEXT_ONLY.value:
        return DisplayIntent.REGULATED.value

    tier = _tier_value(rec.get("evidence_tier"))
    level = _level_value(rec.get("evidence_level"))
    if tier in (EvidenceTier.PRECLINICAL.value, EvidenceTier.RESEARCH_HYPOTHESIS.value):
        return DisplayIntent.MECHANISTIC.value
    if level == EvidenceLevel.PRECLINICAL.value:
        return DisplayIntent.MECHANISTIC.value

    if intent in (RecommendationIntent.PRIMARY.value, RecommendationIntent.NUTRITIONAL_REPLETION.value):
        return DisplayIntent.PRIMARY.value
    if intent == RecommendationIntent.COLLATERAL.value:
        return DisplayIntent.SUPPORTIVE.value
    return DisplayIntent.CONTEXT_ONLY.value