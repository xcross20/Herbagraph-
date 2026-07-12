"""Unit tests for clinical priority scoring and four-lane decision map."""

import pytest

from app.models.enums import (
    DisplayIntent,
    EvidenceLevel,
    EvidenceTier,
    InterventionCategory,
    SafetyRiskLevel,
)
from app.pipeline.report_decision_map import (
    LANE_DIRECT,
    LANE_LIFESTYLE,
    LANE_REGULATED,
    LANE_SUPPORTIVE,
    assign_intervention_lane,
    build_lane_groups,
    compute_clinical_priority_score,
    enrich_intervention_for_decision_map,
)
from app.pipeline.report_intent import classify_intervention_intent_label
from app.pipeline.report_tiering import build_recommendation_tiers

pytestmark = pytest.mark.unit


def _rec(
    name: str,
    *,
    category=InterventionCategory.SUPPLEMENT,
    evidence_tier=EvidenceTier.ESTABLISHED,
    evidence_level=EvidenceLevel.MODERATE,
    confidence_score=0.7,
    is_regulated=False,
    rank=1,
):
    return {
        "rank": rank,
        "intervention_name": name,
        "category": category.value if hasattr(category, "value") else category,
        "mechanism": f"Mechanism for {name}",
        "evidence_level": evidence_level.value if hasattr(evidence_level, "value") else evidence_level,
        "evidence_tier": evidence_tier.value if hasattr(evidence_tier, "value") else evidence_tier,
        "evidence_tier_label": "Established Evidence",
        "confidence_score": confidence_score,
        "safety_risk": SafetyRiskLevel.LOW.value,
        "is_regulated": is_regulated,
        "cited_study_ids": [],
        "cited_urls": [],
        "safety_notes": [],
        "interactions": [],
    }


def _biomarker_summary(abnormal: list[tuple[str, str]], measured_extra: list[str] | None = None) -> dict:
    measured = [{"biomarker_name": name, "status": status, "value": 1.0} for name, status in abnormal]
    for name in measured_extra or []:
        if not any(m["biomarker_name"] == name for m in measured):
            measured.append({"biomarker_name": name, "status": "normal", "value": 1.0})
    return {
        "total_biomarkers": len(measured),
        "abnormal_count": len(abnormal),
        "normal_count": len(measured) - len(abnormal),
        "measured_biomarkers": measured,
    }


def test_regulated_medication_assigned_to_regulated_lane():
    rec = _rec("Atorvastatin", category=InterventionCategory.MEDICATION, is_regulated=True)
    abnormal = {"LDL Cholesterol"}
    display = DisplayIntent.REGULATED.value
    assert assign_intervention_lane(rec, display_intent=display, abnormal_names=abnormal) == LANE_REGULATED
    assert classify_intervention_intent_label(rec, abnormal) == "Regulated Context Only"


def test_lifestyle_intervention_assigned_to_lifestyle_lane():
    rec = _rec("Portfolio Diet", category=InterventionCategory.BEHAVIOR)
    abnormal = {"LDL Cholesterol"}
    display = DisplayIntent.PRIMARY.value
    assert assign_intervention_lane(rec, display_intent=display, abnormal_names=abnormal) == LANE_LIFESTYLE
    assert classify_intervention_intent_label(rec, abnormal) == "Lifestyle Foundation"


def test_iron_and_lactoferrin_score_higher_than_collateral_when_iron_low():
    abnormal = {"Iron"}
    measured = {"Iron", "Glucose"}
    iron = enrich_intervention_for_decision_map(_rec("Iron"), abnormal, measured)
    lacto = enrich_intervention_for_decision_map(_rec("Lactoferrin"), abnormal, measured)
    collateral = enrich_intervention_for_decision_map(_rec("Anthocyanins", category=InterventionCategory.PHYTOCHEMICAL), abnormal, measured)

    assert lacto["clinical_priority_score"] >= iron["clinical_priority_score"]
    assert iron["clinical_priority_score"] > collateral["clinical_priority_score"]
    assert lacto["intervention_lane"] == LANE_DIRECT
    assert collateral["intervention_lane"] == LANE_SUPPORTIVE


def test_regulated_penalty_lowers_clinical_priority_score():
    abnormal = {"LDL Cholesterol"}
    regulated = compute_clinical_priority_score(
        _rec("Atorvastatin", category=InterventionCategory.MEDICATION, is_regulated=True),
        abnormal,
        display_intent=DisplayIntent.REGULATED.value,
    )
    lifestyle = compute_clinical_priority_score(
        _rec("Exercise", category=InterventionCategory.EXERCISE),
        abnormal,
        display_intent=DisplayIntent.PRIMARY.value,
    )
    assert regulated["clinical_priority_score"] < lifestyle["clinical_priority_score"]


def test_build_lane_groups_top_three_default():
    abnormal = {"Iron", "HbA1c"}
    measured = abnormal | {"Glucose"}
    enriched = [
        enrich_intervention_for_decision_map(_rec("Iron", rank=1), abnormal, measured),
        enrich_intervention_for_decision_map(_rec("Lactoferrin", rank=2), abnormal, measured),
        enrich_intervention_for_decision_map(_rec("Berberine", rank=3), abnormal, measured),
        enrich_intervention_for_decision_map(_rec("Magnesium", rank=4), abnormal, measured),
        enrich_intervention_for_decision_map(_rec("Sulforaphane", category=InterventionCategory.PHYTOCHEMICAL, rank=5), abnormal, measured),
        enrich_intervention_for_decision_map(_rec("Exercise", category=InterventionCategory.EXERCISE, rank=6), abnormal, measured),
        enrich_intervention_for_decision_map(_rec("Atorvastatin", category=InterventionCategory.MEDICATION, is_regulated=True, rank=7), abnormal, measured),
    ]
    lanes = build_lane_groups(enriched, top_per_lane=3)

    assert len(lanes[LANE_DIRECT]["items"]) <= 3
    assert lanes[LANE_DIRECT]["hidden_count"] >= 0
    assert lanes[LANE_REGULATED]["items"][0]["intervention_name"] == "Atorvastatin"
    assert lanes[LANE_REGULATED]["total_count"] == 1


def test_build_recommendation_tiers_uses_decision_map_model():
    recommendations = [
        _rec("Iron", rank=1, confidence_score=0.85),
        _rec("Lactoferrin", rank=2, confidence_score=0.82),
        _rec("Berberine", rank=3, confidence_score=0.8),
        _rec("Magnesium", rank=4),
        _rec("Portfolio Diet", category=InterventionCategory.BEHAVIOR, rank=5),
        _rec("Exercise", category=InterventionCategory.EXERCISE, rank=6),
        _rec("Sulforaphane", category=InterventionCategory.PHYTOCHEMICAL, rank=7),
        _rec("Atorvastatin", category=InterventionCategory.MEDICATION, is_regulated=True, rank=8),
    ]
    tiers = build_recommendation_tiers(
        recommendations,
        _biomarker_summary([("Iron", "low"), ("HbA1c", "high"), ("LDL Cholesterol", "high")]),
        [
            {"system_code": "metabolic_health", "system_name": "Metabolic Health", "signal_level": 2, "drivers": ["HbA1c"]},
            {"system_code": "nutrient_status", "system_name": "Nutrient Status", "signal_level": 2, "drivers": ["Iron"]},
        ],
        executive_summary="Integrated iron and metabolic abnormalities.",
    )

    assert tiers["model"] == "decision_map_v1"
    assert "lanes" in tiers
    assert tiers["lanes"][LANE_DIRECT]["short_label"] == "Direct Biomarker Priorities"
    assert len(tiers["lanes"][LANE_DIRECT]["items"]) <= 3
    assert tiers["displayed_by_default"] <= 12
    assert tiers["total_considerations"] == 8
    direct_names = [r["intervention_name"] for r in tiers["lanes"][LANE_DIRECT]["all_items"]]
    assert "Iron" in direct_names
    assert "Lactoferrin" in direct_names
    regulated_names = {r["intervention_name"] for r in tiers["regulated_context"]["items"]}
    assert "Atorvastatin" in regulated_names
    assert all(r.get("clinical_priority_score") is not None for r in tiers["lanes"][LANE_DIRECT]["items"])
    assert all(r.get("intent_label") for r in tiers["lanes"][LANE_DIRECT]["items"])