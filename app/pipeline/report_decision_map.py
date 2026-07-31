"""Clinical priority scoring and four-lane intervention decision map.

Evidence strength alone must not dominate ranking. Interventions are scored by patient
relevance, biomarker directness, pathway fit, safety, and actionability — then partitioned
into clinician-facing lanes (direct, lifestyle, supportive, regulated).
"""

from __future__ import annotations

import re

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
from app.pipeline.report_biological_hierarchy import intervention_network_metrics
from app.pipeline.report_intent import (
    REGULATED_CATEGORIES,
    classify_display_intent,
    classify_intervention_intent_label,
)

_ALL_CLAIMS = [*EVIDENCE_CLAIMS, *TIER_A_EVIDENCE_CLAIMS, *LIFESTYLE_EVIDENCE_CLAIMS]

LANE_DIRECT = "direct_biomarker"
LANE_LIFESTYLE = "lifestyle"
LANE_SUPPORTIVE = "supportive_adjunct"
LANE_REGULATED = "regulated_context"

LANE_LABELS: dict[str, dict[str, str]] = {
    LANE_DIRECT: {
        "label": "Directly Relevant to Abnormal Biomarkers",
        "short_label": "Direct Biomarker Priorities",
    },
    LANE_LIFESTYLE: {
        "label": "High-Leverage Lifestyle / Nutrition",
        "short_label": "Lifestyle Foundations",
    },
    LANE_SUPPORTIVE: {
        "label": "Supportive / Mechanistic Adjuncts",
        "short_label": "Supportive Adjuncts",
    },
    LANE_REGULATED: {
        "label": "Regulated / Clinical Context Only",
        "short_label": "Regulated Clinical Context",
    },
}

_LIFESTYLE_CATEGORIES = frozenset({
    InterventionCategory.EXERCISE.value,
    InterventionCategory.SLEEP.value,
    InterventionCategory.STRESS_REDUCTION.value,
    InterventionCategory.BEHAVIOR.value,
    InterventionCategory.ENVIRONMENTAL.value,
})

_DIET_PATTERN_RE = re.compile(
    r"diet|eating|fasting|mediterranean|portfolio|plant-based|dash|low-carb|time-restricted",
    re.IGNORECASE,
)

_IRON_PANEL = frozenset({
    "Iron",
    "Ferritin",
    "Hemoglobin",
    "Transferrin Saturation",
    "TIBC",
    "UIBC",
    "RDW",
    "Hematocrit",
})

_BIOMARKER_PANELS: list[frozenset[str]] = [
    _IRON_PANEL,
    frozenset({"HbA1c", "Glucose", "Fasting Insulin", "Triglycerides"}),
    frozenset({"LDL Cholesterol", "LDL", "ApoB", "Triglycerides", "HDL Cholesterol"}),
]

_INTERVENTION_PANEL_HINTS: dict[str, frozenset[str]] = {
    "Iron": _IRON_PANEL,
    "Lactoferrin": _IRON_PANEL,
}

_IRON_BIOMARKERS = _IRON_PANEL

_SCORE_WEIGHTS = {
    "patient_relevance": 22.0,
    "biomarker_directness": 22.0,
    "pathway_relevance": 14.0,
    "evidence_strength": 12.0,
    "safety": 10.0,
    "actionability": 10.0,
}

_REGULATED_PENALTY = 25.0
_UNCERTAINTY_PENALTY_MAX = 15.0

_SAFETY_SCORE = {
    "low": 1.0,
    "moderate": 0.72,
    "high": 0.35,
    "contraindicated": 0.0,
}

_INTENT_RANK = {
    RecommendationIntent.PRIMARY.value: 0,
    RecommendationIntent.NUTRITIONAL_REPLETION.value: 1,
    RecommendationIntent.COLLATERAL.value: 2,
    RecommendationIntent.CONTEXT_ONLY.value: 3,
}

_INTENT_RELEVANCE = {
    RecommendationIntent.PRIMARY.value: 1.0,
    RecommendationIntent.NUTRITIONAL_REPLETION.value: 0.96,
    RecommendationIntent.COLLATERAL.value: 0.52,
    RecommendationIntent.CONTEXT_ONLY.value: 0.22,
}

_EVIDENCE_HUMAN_SCORE = {
    (EvidenceTier.ESTABLISHED.value, EvidenceLevel.HIGH.value): 1.0,
    (EvidenceTier.ESTABLISHED.value, EvidenceLevel.MODERATE.value): 0.92,
    (EvidenceTier.ESTABLISHED.value, EvidenceLevel.LOW.value): 0.78,
    (EvidenceTier.EMERGING.value, EvidenceLevel.HIGH.value): 0.72,
    (EvidenceTier.EMERGING.value, EvidenceLevel.MODERATE.value): 0.62,
    (EvidenceTier.EMERGING.value, EvidenceLevel.LOW.value): 0.48,
    (EvidenceTier.PRECLINICAL.value, EvidenceLevel.MODERATE.value): 0.28,
    (EvidenceTier.PRECLINICAL.value, EvidenceLevel.LOW.value): 0.2,
    (EvidenceTier.PRECLINICAL.value, EvidenceLevel.PRECLINICAL.value): 0.15,
}

TOP_PER_LANE_DEFAULT = 3


def _tier_value(tier) -> str:
    return tier.value if hasattr(tier, "value") else str(tier or EvidenceTier.RESEARCH_HYPOTHESIS.value)


def _level_value(level) -> str:
    return level.value if hasattr(level, "value") else str(level or EvidenceLevel.LOW.value)


def _category_value(category) -> str:
    return category.value if hasattr(category, "value") else str(category or "")


def _abnormal_biomarkers(biomarker_summary: dict) -> list[dict]:
    abnormal_statuses = {"critical_low", "low", "high", "critical_high"}
    return [
        m
        for m in biomarker_summary.get("measured_biomarkers", [])
        if m.get("status") in abnormal_statuses
    ]


def _expanded_abnormal_context(abnormal_names: set[str]) -> set[str]:
    """Expand abnormal markers to clinically linked panel members (e.g. Iron ↔ Ferritin)."""
    expanded = set(abnormal_names)
    for panel in _BIOMARKER_PANELS:
        if panel & abnormal_names:
            expanded |= panel
    return expanded


def _claim_matches_abnormal(claim: dict, abnormal_names: set[str], intervention_name: str) -> bool:
    biomarker = claim.get("biomarker_name")
    if biomarker in abnormal_names:
        return True
    context = _expanded_abnormal_context(abnormal_names)
    if biomarker in context:
        panel_hint = _INTERVENTION_PANEL_HINTS.get(intervention_name)
        if panel_hint and biomarker in panel_hint:
            return True
    return False


def _claims_for_intervention(name: str, abnormal_names: set[str]) -> list[dict]:
    return [
        c
        for c in _ALL_CLAIMS
        if c["intervention_name"] == name
        and (
            _claim_matches_abnormal(c, abnormal_names, name)
            or (c.get("biomarker_name") is None and not abnormal_names)
        )
    ]


def _direct_abnormal_claims(name: str, abnormal_names: set[str]) -> list[dict]:
    return [
        c
        for c in _ALL_CLAIMS
        if c["intervention_name"] == name and _claim_matches_abnormal(c, abnormal_names, name)
    ]


def _is_lifestyle_intervention(rec: dict) -> bool:
    category = _category_value(rec.get("category"))
    name = rec.get("intervention_name", "")
    if category in _LIFESTYLE_CATEGORIES:
        return True
    if category == InterventionCategory.FOOD.value and _DIET_PATTERN_RE.search(name):
        return True
    return bool(_DIET_PATTERN_RE.search(name))


def _recommendation_intent_for(name: str, abnormal_names: set[str]) -> str:
    """Patient-specific intent — ignores biomarker-agnostic claims when abnormalities exist."""
    if abnormal_names:
        matching = [
            c
            for c in _ALL_CLAIMS
            if c["intervention_name"] == name and _claim_matches_abnormal(c, abnormal_names, name)
        ]
    else:
        matching = [c for c in _ALL_CLAIMS if c["intervention_name"] == name]
    if not matching:
        return RecommendationIntent.COLLATERAL.value
    best = min(matching, key=lambda c: _INTENT_RANK.get(c.get("recommendation_intent", "collateral"), 9))
    return best.get("recommendation_intent", RecommendationIntent.COLLATERAL.value)


def _patient_relevance(rec: dict, abnormal_names: set[str], metrics: dict) -> float:
    intent = _recommendation_intent_for(rec.get("intervention_name", ""), abnormal_names)
    base = _INTENT_RELEVANCE.get(intent, 0.45)
    if metrics.get("biomarkers_explained", 0) > 0:
        base = min(1.0, base + 0.12)
    if _direct_abnormal_claims(rec.get("intervention_name", ""), abnormal_names):
        base = min(1.0, base + 0.08)
    return base


def _biomarker_directness(rec: dict, abnormal_names: set[str]) -> float:
    if not abnormal_names:
        return 0.35
    name = rec.get("intervention_name", "")
    direct = _direct_abnormal_claims(name, abnormal_names)
    if not direct:
        return 0.2
    matched = {c["biomarker_name"] for c in direct if c.get("biomarker_name")}
    panel_hint = _INTERVENTION_PANEL_HINTS.get(name)
    if panel_hint and panel_hint & abnormal_names:
        return min(1.0, 0.72 + len(matched) * 0.06)
    return min(1.0, len(matched) / max(len(abnormal_names), 1) + 0.35)


def _pathway_relevance(metrics: dict) -> float:
    coverage = float(metrics.get("biomarker_coverage") or 0.0)
    pathway_cov = float(metrics.get("pathway_coverage") or 0.0)
    biology = min(1.0, float(metrics.get("biology_weight") or 0.0) / 2.5)
    return min(1.0, coverage * 0.45 + pathway_cov * 0.3 + biology * 0.25)


def _evidence_strength(rec: dict) -> float:
    tier = _tier_value(rec.get("evidence_tier"))
    level = _level_value(rec.get("evidence_level"))
    return _EVIDENCE_HUMAN_SCORE.get((tier, level), 0.18 if tier == EvidenceTier.EMERGING.value else 0.12)


def _safety_component(rec: dict) -> float:
    return _SAFETY_SCORE.get(str(rec.get("safety_risk") or "low").lower(), 0.5)


def _actionability(rec: dict, display_intent: str) -> float:
    category = _category_value(rec.get("category"))
    if display_intent == DisplayIntent.REGULATED.value:
        return 0.15
    if _is_lifestyle_intervention(rec):
        return 0.95
    if category in {
        InterventionCategory.FOOD.value,
        InterventionCategory.SUPPLEMENT.value,
        InterventionCategory.HERB.value,
        InterventionCategory.PHYTOCHEMICAL.value,
    }:
        return 0.82
    return 0.55


def _uncertainty_penalty(rec: dict) -> float:
    tier = _tier_value(rec.get("evidence_tier"))
    level = _level_value(rec.get("evidence_level"))
    confidence = float(rec.get("confidence_score") or 0.5)
    penalty = 0.0
    if tier in (EvidenceTier.PRECLINICAL.value, EvidenceTier.RESEARCH_HYPOTHESIS.value):
        penalty += 8.0
    if level == EvidenceLevel.PRECLINICAL.value:
        penalty += 4.0
    if confidence < 0.45:
        penalty += 6.0
    elif confidence < 0.6:
        penalty += 3.0
    return min(_UNCERTAINTY_PENALTY_MAX, penalty)


def _regulated_penalty(rec: dict, display_intent: str) -> float:
    category = _category_value(rec.get("category"))
    if display_intent == DisplayIntent.REGULATED.value or rec.get("is_regulated"):
        return _REGULATED_PENALTY
    if category in REGULATED_CATEGORIES:
        return _REGULATED_PENALTY
    return 0.0


def _iron_pathway_boost(rec: dict, abnormal_names: set[str], measured_names: set[str]) -> float:
    """Boost iron-clarification interventions when iron biology is implicated."""
    name = rec.get("intervention_name", "")
    iron_abnormal = bool(abnormal_names & _IRON_BIOMARKERS)
    if not iron_abnormal:
        return 0.0
    if name == "Lactoferrin":
        ferritin_missing = "Ferritin" not in measured_names
        if ferritin_missing or "Iron" in abnormal_names:
            return 8.0
        return 5.0
    if name == "Iron":
        return 4.0
    return 0.0


def compute_clinical_priority_score(
    rec: dict,
    abnormal_names: set[str],
    *,
    display_intent: str,
    metrics: dict | None = None,
    measured_names: set[str] | None = None,
) -> dict:
    """Return 0–100 clinical priority score and component breakdown."""
    metrics = metrics or {}
    measured_names = measured_names or set()

    components = {
        "patient_relevance": _patient_relevance(rec, abnormal_names, metrics),
        "biomarker_directness": _biomarker_directness(rec, abnormal_names),
        "pathway_relevance": _pathway_relevance(metrics),
        "evidence_strength": _evidence_strength(rec),
        "safety": _safety_component(rec),
        "actionability": _actionability(rec, display_intent),
    }

    raw = sum(components[k] * _SCORE_WEIGHTS[k] for k in _SCORE_WEIGHTS)
    raw += _iron_pathway_boost(rec, abnormal_names, measured_names)
    raw -= _regulated_penalty(rec, display_intent)
    raw -= _uncertainty_penalty(rec)
    score = max(0, min(100, round(raw)))

    return {
        "clinical_priority_score": score,
        "priority_components": {k: round(v, 3) for k, v in components.items()},
    }


def evidence_strength_label(rec: dict) -> str:
    tier = _tier_value(rec.get("evidence_tier"))
    level = _level_value(rec.get("evidence_level"))
    if tier == EvidenceTier.ESTABLISHED.value or level == EvidenceLevel.HIGH.value:
        return "Strong Human"
    if tier == EvidenceTier.EMERGING.value:
        return "Emerging Human"
    if tier in (EvidenceTier.PRECLINICAL.value, EvidenceTier.RESEARCH_HYPOTHESIS.value):
        return "Mechanistic / Preclinical"
    return "Moderate Human"


def patient_fit_label(rec: dict, abnormal_names: set[str], metrics: dict) -> str:
    directness = _biomarker_directness(rec, abnormal_names)
    explained = int(metrics.get("biomarkers_explained") or 0)
    if directness >= 0.75 or explained >= 2:
        return "High"
    if directness >= 0.45 or explained >= 1:
        return "Moderate"
    return "Low"


def safety_display_label(rec: dict) -> str:
    risk = str(rec.get("safety_risk") or "low").lower()
    if risk == "low":
        return "Low Risk"
    if risk == "moderate":
        return "Moderate Risk"
    if risk == "high":
        return "Higher Risk"
    return "Contraindicated"


def assign_intervention_lane(
    rec: dict,
    *,
    display_intent: str,
    abnormal_names: set[str],
) -> str:
    """Partition into one of four clinician-facing lanes."""
    category = _category_value(rec.get("category"))
    name = rec.get("intervention_name", "")

    if (
        display_intent == DisplayIntent.REGULATED.value
        or rec.get("is_regulated")
        or category in REGULATED_CATEGORIES
    ):
        return LANE_REGULATED

    rec_intent = _recommendation_intent_for(name, abnormal_names)
    has_direct = bool(_direct_abnormal_claims(name, abnormal_names))

    if _is_lifestyle_intervention(rec):
        return LANE_LIFESTYLE

    if has_direct and rec_intent in (
        RecommendationIntent.PRIMARY.value,
        RecommendationIntent.NUTRITIONAL_REPLETION.value,
    ):
        if display_intent in (DisplayIntent.MECHANISTIC.value, DisplayIntent.CONTEXT_ONLY.value):
            return LANE_SUPPORTIVE
        return LANE_DIRECT

    if display_intent in (DisplayIntent.MECHANISTIC.value, DisplayIntent.SUPPORTIVE.value):
        return LANE_SUPPORTIVE

    if rec_intent == RecommendationIntent.COLLATERAL.value:
        return LANE_SUPPORTIVE

    return LANE_SUPPORTIVE


def enrich_intervention_for_decision_map(
    rec: dict,
    abnormal_names: set[str],
    measured_names: set[str],
    *,
    intervention_pathways: dict[str, list[str]] | None = None,
    pathway_index: dict[str, dict] | None = None,
) -> dict:
    """Attach clinical priority score, lane, intent label, and display badges."""
    row = dict(rec)
    display_intent = classify_display_intent(rec, abnormal_names)
    row["display_intent"] = display_intent

    metrics: dict = {}
    if intervention_pathways is not None and pathway_index is not None:
        metrics = intervention_network_metrics(rec, intervention_pathways, pathway_index, abnormal_names)
        row["pathways_hit"] = metrics["pathways_hit"]
        row["biomarkers_explained"] = metrics["biomarkers_explained"]
        row["biomarkers_explained_names"] = metrics["biomarkers_explained_names"]

    priority = compute_clinical_priority_score(
        rec,
        abnormal_names,
        display_intent=display_intent,
        metrics=metrics,
        measured_names=measured_names,
    )
    row.update(priority)
    row["intervention_lane"] = assign_intervention_lane(rec, display_intent=display_intent, abnormal_names=abnormal_names)
    row["intent_label"] = classify_intervention_intent_label(rec, abnormal_names, display_intent=display_intent)
    row["evidence_strength_label"] = evidence_strength_label(rec)
    row["patient_fit_label"] = patient_fit_label(rec, abnormal_names, metrics)
    row["safety_display_label"] = safety_display_label(rec)
    return row


def build_lane_groups(
    enriched: list[dict],
    *,
    top_per_lane: int = TOP_PER_LANE_DEFAULT,
) -> dict[str, dict]:
    """Group enriched interventions into four lanes with top-N defaults."""
    buckets: dict[str, list[dict]] = {lane: [] for lane in LANE_LABELS}
    for row in enriched:
        lane = row.get("intervention_lane", LANE_SUPPORTIVE)
        buckets.setdefault(lane, []).append(row)

    for lane, items in buckets.items():
        items.sort(
            key=lambda r: (
                -r.get("clinical_priority_score", 0),
                r.get("rank", 999),
            )
        )
        for index, item in enumerate(items, start=1):
            item["lane_rank"] = index

    lanes: dict[str, dict] = {}
    for lane_code, meta in LANE_LABELS.items():
        all_items = buckets.get(lane_code, [])
        top_items = all_items[:top_per_lane]
        hidden = max(0, len(all_items) - len(top_items))
        lanes[lane_code] = {
            **meta,
            "lane_code": lane_code,
            "items": top_items,
            "all_items": all_items,
            "hidden_count": hidden,
            "total_count": len(all_items),
        }
    return lanes