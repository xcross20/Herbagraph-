"""Tiered report presentation — prioritize clinically actionable considerations.

The graph may surface dozens of evidence-graded items; the default report shows only
the highest-value subset with expandable category groups and a separate regulated context.
"""

from __future__ import annotations

import re

from app.pipeline.report_biological_hierarchy import biology_first_network_score, intervention_network_metrics
from app.pipeline.report_intent import classify_display_intent, recommendation_intent_for
from app.models.enums import (
    DisplayIntent,
    EvidenceLevel,
    EvidenceTier,
    InterventionCategory,
    RecommendationIntent,
)

TOP_CONSIDERATIONS_MIN = 5
TOP_CONSIDERATIONS_MAX = 10
TOP_CONSIDERATIONS_DEFAULT = 7
PER_CATEGORY_MAX = 3
TOP_BIOLOGICAL_PROBLEMS = 3
_CLINICAL_SUMMARY_MAX_CHARS = 900

_CATEGORY_BUCKETS: dict[str, str] = {
    InterventionCategory.FOOD.value: "foods_dietary",
    InterventionCategory.PHYTOCHEMICAL.value: "foods_dietary",
    InterventionCategory.HERB.value: "botanicals",
    InterventionCategory.SUPPLEMENT.value: "nutraceuticals",
    InterventionCategory.EXERCISE.value: "lifestyle",
    InterventionCategory.SLEEP.value: "lifestyle",
    InterventionCategory.STRESS_REDUCTION.value: "lifestyle",
    InterventionCategory.BEHAVIOR.value: "lifestyle",
    InterventionCategory.ENVIRONMENTAL.value: "lifestyle",
    InterventionCategory.MEDICATION.value: "regulated_therapies",
    InterventionCategory.PEPTIDE.value: "regulated_therapies",
    InterventionCategory.HORMONE.value: "regulated_therapies",
}

_BUCKET_LABELS: dict[str, str] = {
    "foods_dietary": "Foods / dietary compounds",
    "botanicals": "Botanicals",
    "nutraceuticals": "Nutraceuticals",
    "lifestyle": "Lifestyle",
    "regulated_therapies": "Regulated therapies",
    "mechanistic_only": "Mechanistic-only ideas",
}

_INTENT_RANK = {
    RecommendationIntent.PRIMARY.value: 0,
    RecommendationIntent.NUTRITIONAL_REPLETION.value: 1,
    RecommendationIntent.COLLATERAL.value: 2,
    RecommendationIntent.CONTEXT_ONLY.value: 3,
}

_EVIDENCE_TIER_RANK = {
    EvidenceTier.ESTABLISHED.value: 0,
    EvidenceTier.EMERGING.value: 1,
    EvidenceTier.PRECLINICAL.value: 2,
    EvidenceTier.RESEARCH_HYPOTHESIS.value: 3,
}

_EVIDENCE_LEVEL_RANK = {
    EvidenceLevel.HIGH.value: 0,
    EvidenceLevel.MODERATE.value: 1,
    EvidenceLevel.LOW.value: 2,
    EvidenceLevel.PRECLINICAL.value: 3,
}

_SAFETY_PENALTY = {
    "low": 0,
    "moderate": 4,
    "high": 18,
    "contraindicated": 30,
}

_BIOMARKER_PROBLEM_THEMES: dict[str, dict] = {
    "HbA1c": {
        "system_code": "metabolic_health",
        "title": "Metabolic health / insulin signaling",
        "summary": "Elevated HbA1c suggests sustained glycemic dysregulation and insulin pathway stress.",
    },
    "Glucose": {
        "system_code": "metabolic_health",
        "title": "Metabolic health / glycemic control",
        "summary": "Elevated glucose may reflect acute or sustained dysglycemia; HbA1c would clarify chronicity.",
    },
    "LDL Cholesterol": {
        "system_code": "cardiovascular_risk",
        "title": "Cardiovascular / lipid metabolism",
        "summary": "Elevated LDL implicates hepatic lipid handling and cardiovascular risk pathways.",
    },
    "LDL": {
        "system_code": "cardiovascular_risk",
        "title": "Cardiovascular / lipid metabolism",
        "summary": "Elevated LDL implicates hepatic lipid handling and cardiovascular risk pathways.",
    },
    "Iron": {
        "system_code": "nutrient_status",
        "title": "Nutrient status / iron deficiency",
        "summary": "Low iron suggests depleted circulating iron and possible iron-deficiency biology.",
    },
    "Ferritin": {
        "system_code": "nutrient_status",
        "title": "Nutrient status / iron stores",
        "summary": "Low ferritin is consistent with depleted iron stores or inflammation-driven sequestration.",
    },
    "TSH": {
        "system_code": "thyroid_endocrine",
        "title": "Thyroid / endocrine signaling",
        "summary": "Abnormal TSH suggests thyroid axis dysregulation; free T4/T3 would confirm peripheral status.",
    },
    "CRP": {
        "system_code": "inflammation",
        "title": "Inflammation / immune signaling",
        "summary": "Elevated CRP indicates systemic inflammatory pathway activation.",
    },
    "hs-CRP": {
        "system_code": "inflammation",
        "title": "Inflammation / cardiovascular risk",
        "summary": "Elevated hs-CRP reflects low-grade systemic inflammation relevant to cardiometabolic risk.",
    },
}

_SYSTEM_PROBLEM_FALLBACK: dict[str, str] = {
    "metabolic_health": "Metabolic and insulin-signaling pathways show abnormal lab-driven signal.",
    "cardiovascular_risk": "Cardiovascular and lipid-metabolism pathways show abnormal lab-driven signal.",
    "nutrient_status": "Nutrient-status pathways (iron, B-vitamins, vitamin D) show abnormal signal.",
    "inflammation": "Inflammatory signaling pathways show abnormal lab-driven signal.",
    "thyroid_endocrine": "Thyroid/endocrine pathways show abnormal lab-driven signal.",
    "liver_detox_stress": "Hepatic and detoxification stress pathways show signal.",
    "oxidative_stress_mitochondrial": "Oxidative stress and mitochondrial resilience pathways show signal.",
}

def _abnormal_biomarkers(biomarker_summary: dict) -> list[dict]:
    abnormal_statuses = {"critical_low", "low", "high", "critical_high"}
    return [
        m
        for m in biomarker_summary.get("measured_biomarkers", [])
        if m.get("status") in abnormal_statuses
    ]


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


def _mechanism_key(rec: dict) -> str:
    mechanism = (rec.get("mechanism") or rec.get("intervention_name") or "").lower()
    mechanism = re.sub(r"[^a-z0-9]+", " ", mechanism).strip()
    tokens = mechanism.split()[:6]
    return " ".join(tokens) if tokens else (rec.get("intervention_name") or "").lower()


def _biomarker_tie_score(rec: dict, abnormal_biomarkers: set[str]) -> float:
    intent = recommendation_intent_for(rec.get("intervention_name", ""), abnormal_biomarkers)
    if intent in (RecommendationIntent.PRIMARY.value, RecommendationIntent.NUTRITIONAL_REPLETION.value):
        return 1.0
    if intent == RecommendationIntent.COLLATERAL.value:
        return 0.5
    return 0.35


def _actionability_score(rec: dict, display_intent: str) -> float:
    category = _category_value(rec.get("category"))
    if display_intent == DisplayIntent.PRIMARY.value:
        base = 1.0
    elif display_intent == DisplayIntent.SUPPORTIVE.value:
        base = 0.65
    else:
        base = 0.2
    if category in {
        InterventionCategory.FOOD.value,
        InterventionCategory.EXERCISE.value,
        InterventionCategory.SLEEP.value,
        InterventionCategory.BEHAVIOR.value,
    }:
        base += 0.08
    return min(base, 1.0)


def _human_evidence_score(rec: dict) -> float:
    tier = _tier_value(rec.get("evidence_tier"))
    level = _level_value(rec.get("evidence_level"))
    tier_score = {EvidenceTier.ESTABLISHED.value: 1.0, EvidenceTier.EMERGING.value: 0.7}.get(tier, 0.25)
    level_score = {
        EvidenceLevel.HIGH.value: 1.0,
        EvidenceLevel.MODERATE.value: 0.7,
        EvidenceLevel.LOW.value: 0.4,
    }.get(level, 0.15)
    return max(tier_score, level_score)


def _tier_rank_score(rec: dict, display_intent: str, abnormal_biomarkers: set[str]) -> float:
    confidence = float(rec.get("confidence_score") or 0.0)
    safety = str(rec.get("safety_risk") or "low").lower()
    score = (
        confidence * 40.0
        + _biomarker_tie_score(rec, abnormal_biomarkers) * 18.0
        + _actionability_score(rec, display_intent) * 14.0
        + _human_evidence_score(rec) * 12.0
        + (8.0 if display_intent == DisplayIntent.PRIMARY.value else 0.0)
        - _SAFETY_PENALTY.get(safety, 0)
    )
    return round(score, 4)


def _enrich_rec(rec: dict, display_intent: str, tier_rank: float, *, tier_rank_display: int | None = None) -> dict:
    row = dict(rec)
    row["display_intent"] = display_intent
    row["tier_rank_score"] = tier_rank
    if tier_rank_display is not None:
        row["tier_rank"] = tier_rank_display
    return row


def build_top_biological_problems(
    biomarker_summary: dict,
    biological_systems: list[dict],
    *,
    limit: int = TOP_BIOLOGICAL_PROBLEMS,
) -> list[dict]:
    """Top abnormal biomarker themes for the default report header."""
    problems: list[dict] = []
    seen_systems: set[str] = set()

    for marker in _abnormal_biomarkers(biomarker_summary):
        theme = _BIOMARKER_PROBLEM_THEMES.get(marker["biomarker_name"])
        if not theme:
            continue
        code = theme["system_code"]
        if code in seen_systems:
            continue
        seen_systems.add(code)
        problems.append(
            {
                "biomarker_name": marker["biomarker_name"],
                "status": marker.get("status"),
                "system_code": code,
                "title": theme["title"],
                "summary": theme["summary"],
            }
        )

    if len(problems) < limit:
        ranked_systems = sorted(
            biological_systems,
            key=lambda s: (-(s.get("signal_level") or 0), s.get("system_name", "")),
        )
        for system in ranked_systems:
            if len(problems) >= limit:
                break
            code = system.get("system_code", "")
            if (system.get("signal_level") or 0) <= 0 or code in seen_systems:
                continue
            seen_systems.add(code)
            problems.append(
                {
                    "biomarker_name": (system.get("drivers") or ["Panel signal"])[0],
                    "status": "signal",
                    "system_code": code,
                    "title": system.get("system_name", code),
                    "summary": _SYSTEM_PROBLEM_FALLBACK.get(
                        code,
                        f"{system.get('system_name', 'Biological system')} shows evidence-weighted pathway signal.",
                    ),
                }
            )

    return problems[:limit]


def _condense_executive_summary(
    executive_summary: str,
    top_problems: list[dict],
    top_count: int,
    total_count: int,
) -> str:
    text = (executive_summary or "").strip()
    if len(text) > _CLINICAL_SUMMARY_MAX_CHARS:
        sentences = re.split(r"(?<=[.!?])\s+", text)
        text = " ".join(sentences[:4]).strip()

    if top_problems:
        themes = "; ".join(p["title"] for p in top_problems[:3])
        lead = f"Main biological themes: {themes}."
        if text:
            text = f"{lead} {text}"
        else:
            text = lead

    if total_count > top_count:
        text = (
            f"{text} Showing top {top_count} of {total_count} evidence-graded considerations by default; "
            "expand sections below for additional evidence."
        ).strip()
    return text


def _select_top_considerations(
    pool: list[dict],
    *,
    min_count: int = TOP_CONSIDERATIONS_MIN,
    max_count: int = TOP_CONSIDERATIONS_MAX,
    default_count: int = TOP_CONSIDERATIONS_DEFAULT,
) -> list[dict]:
    target = min(max(default_count, min_count), max_count, len(pool))
    selected: list[dict] = []
    used_names: set[str] = set()
    used_mechanisms: set[str] = set()

    for rec in pool:
        if len(selected) >= target:
            break
        name = (rec.get("intervention_name") or "").lower()
        mech = _mechanism_key(rec)
        if name in used_names:
            continue
        if mech in used_mechanisms and len(selected) >= min_count:
            continue
        used_names.add(name)
        used_mechanisms.add(mech)
        selected.append(rec)

    if len(selected) < min_count:
        for rec in pool:
            if len(selected) >= min_count:
                break
            name = (rec.get("intervention_name") or "").lower()
            if name in used_names:
                continue
            used_names.add(name)
            selected.append(rec)
    return selected


def build_recommendation_tiers(
    recommendations: list[dict],
    biomarker_summary: dict,
    biological_systems: list[dict],
    *,
    executive_summary: str = "",
    intervention_pathways: dict[str, list[str]] | None = None,
    pathway_activations: list[dict] | None = None,
) -> dict:
    """Partition ranked recommendations into clinician-friendly default vs expandable views."""
    abnormal_names = {m["biomarker_name"] for m in _abnormal_biomarkers(biomarker_summary)}
    total = len(recommendations)
    pathway_index = {
        p["pathway_code"]: p
        for p in (pathway_activations or [])
        if (p.get("activation_score") or 0) > 0
    }
    use_network_rank = bool(intervention_pathways and pathway_index)

    regulated: list[dict] = []
    mechanistic: list[dict] = []
    actionable_pool: list[dict] = []

    for rec in recommendations:
        display_intent = classify_display_intent(rec, abnormal_names)
        if use_network_rank:
            tier_rank = biology_first_network_score(
                rec,
                intervention_pathways or {},
                pathway_index,
                abnormal_names,
                display_intent=display_intent,
            )
        else:
            tier_rank = _tier_rank_score(rec, display_intent, abnormal_names)
        row = _enrich_rec(rec, display_intent, tier_rank)
        if use_network_rank:
            metrics = intervention_network_metrics(
                rec, intervention_pathways or {}, pathway_index, abnormal_names
            )
            row["pathways_hit"] = metrics["pathways_hit"]
            row["biomarkers_explained"] = metrics["biomarkers_explained"]

        if display_intent == DisplayIntent.REGULATED.value:
            regulated.append(row)
        elif display_intent == DisplayIntent.MECHANISTIC.value:
            mechanistic.append(row)
        elif display_intent == DisplayIntent.CONTEXT_ONLY.value:
            mechanistic.append(row)
        else:
            actionable_pool.append(row)

    actionable_pool.sort(
        key=lambda r: (
            _INTENT_RANK.get(
                recommendation_intent_for(r.get("intervention_name", ""), abnormal_names),
                9,
            ),
            -r.get("tier_rank_score", 0),
            _EVIDENCE_TIER_RANK.get(_tier_value(r.get("evidence_tier")), 9),
            r.get("rank", 999),
        )
    )

    top_considerations = _select_top_considerations(actionable_pool)
    top_names = {(r.get("intervention_name") or "").lower() for r in top_considerations}

    remaining_actionable = [r for r in actionable_pool if (r.get("intervention_name") or "").lower() not in top_names]
    additional_by_category: dict[str, dict] = {}
    for rec in remaining_actionable:
        if rec.get("display_intent") == DisplayIntent.MECHANISTIC.value:
            bucket = "mechanistic_only"
        else:
            bucket = _CATEGORY_BUCKETS.get(_category_value(rec.get("category")), "nutraceuticals")
        group = additional_by_category.setdefault(
            bucket,
            {"label": _BUCKET_LABELS[bucket], "items": [], "hidden_count": 0},
        )
        if len(group["items"]) < PER_CATEGORY_MAX:
            group["items"].append(rec)
        else:
            group["hidden_count"] += 1

    for rec in mechanistic:
        group = additional_by_category.setdefault(
            "mechanistic_only",
            {"label": _BUCKET_LABELS["mechanistic_only"], "items": [], "hidden_count": 0},
        )
        if len(group["items"]) < PER_CATEGORY_MAX:
            group["items"].append(rec)
        else:
            group["hidden_count"] += 1

    top_problems = build_top_biological_problems(biomarker_summary, biological_systems)
    top_count = len(top_considerations)

    for index, rec in enumerate(top_considerations, start=1):
        rec["tier_rank"] = index

    displayed_default = top_count + sum(len(g["items"]) for g in additional_by_category.values())

    return {
        "model": "tiered_v1",
        "caps": {
            "top_considerations_min": TOP_CONSIDERATIONS_MIN,
            "top_considerations_max": TOP_CONSIDERATIONS_MAX,
            "top_considerations_default": TOP_CONSIDERATIONS_DEFAULT,
            "per_category_max": PER_CATEGORY_MAX,
            "top_biological_problems": TOP_BIOLOGICAL_PROBLEMS,
        },
        "top_biological_problems": top_problems,
        "top_considerations": top_considerations,
        "additional_by_category": additional_by_category,
        "regulated_context": {
            "label": "Conventional / Regulated Context",
            "disclaimer": (
                "Prescription and regulated therapies are shown for clinical context only, "
                "not as self-directed treatment recommendations."
            ),
            "items": regulated,
        },
        "mechanistic_appendix": {
            "label": "Mechanistic / preclinical evidence",
            "hidden_by_default": True,
            "items": mechanistic,
        },
        "full_appendix_available": total > displayed_default,
        "total_considerations": total,
        "displayed_by_default": displayed_default,
        "clinical_executive_summary": _condense_executive_summary(
            executive_summary,
            top_problems,
            top_count,
            total,
        ),
    }