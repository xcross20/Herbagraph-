"""Unit tests for tiered report presentation."""

import pytest

from app.models.enums import (
    DisplayIntent,
    EvidenceLevel,
    EvidenceTier,
    InterventionCategory,
    SafetyRiskLevel,
)
from app.pipeline.report_intent import classify_display_intent
from app.pipeline.report_tiering import (
    TOP_CONSIDERATIONS_MAX,
    build_recommendation_tiers,
    build_top_biological_problems,
)

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
    mechanism="Test mechanism",
):
    return {
        "rank": rank,
        "intervention_name": name,
        "category": category.value if hasattr(category, "value") else category,
        "mechanism": mechanism,
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


def _biomarker_summary(abnormal_names: list[str]) -> dict:
    measured = []
    for name in abnormal_names:
        measured.append({"biomarker_name": name, "status": "high", "value": 1.0})
    measured.append({"biomarker_name": "Glucose", "status": "normal", "value": 90.0})
    return {
        "total_biomarkers": len(measured),
        "abnormal_count": len(abnormal_names),
        "normal_count": len(measured) - len(abnormal_names),
        "measured_biomarkers": measured,
    }


def test_classify_regulated_medication_as_regulated():
    rec = _rec("Atorvastatin", category=InterventionCategory.MEDICATION, is_regulated=True)
    intent = classify_display_intent(rec, {"LDL Cholesterol"})
    assert intent == DisplayIntent.REGULATED.value


def test_classify_preclinical_as_mechanistic():
    rec = _rec(
        "Obscure Compound",
        evidence_tier=EvidenceTier.PRECLINICAL,
        evidence_level=EvidenceLevel.PRECLINICAL,
    )
    intent = classify_display_intent(rec, {"HbA1c"})
    assert intent == DisplayIntent.MECHANISTIC.value


def test_top_considerations_capped_for_large_pool():
    recommendations = []
    for i in range(40):
        recommendations.append(
            _rec(
                f"Supplement-{i}",
                rank=i + 1,
                confidence_score=0.9 - i * 0.01,
                mechanism=f"Unique mechanism number {i}",
            )
        )
    recommendations.extend(
        [
            _rec("Atorvastatin", category=InterventionCategory.MEDICATION, is_regulated=True, rank=41),
            _rec("Metformin", category=InterventionCategory.MEDICATION, is_regulated=True, rank=42),
            _rec("Empagliflozin", category=InterventionCategory.MEDICATION, is_regulated=True, rank=43),
        ]
    )

    tiers = build_recommendation_tiers(
        recommendations,
        _biomarker_summary(["HbA1c", "LDL Cholesterol", "Iron"]),
        [
            {"system_code": "metabolic_health", "system_name": "Metabolic Health", "signal_level": 2, "drivers": ["HbA1c"]},
            {"system_code": "cardiovascular_risk", "system_name": "Cardiovascular Risk", "signal_level": 2, "drivers": ["LDL Cholesterol"]},
            {"system_code": "nutrient_status", "system_name": "Nutrient Status", "signal_level": 1, "drivers": ["Iron"]},
        ],
        executive_summary="Integrated analysis across three abnormal biomarkers.",
    )

    assert len(tiers["top_considerations"]) <= TOP_CONSIDERATIONS_MAX
    assert len(tiers["top_considerations"]) >= 5
    assert tiers["total_considerations"] == 43
    regulated_names = {r["intervention_name"] for r in tiers["regulated_context"]["items"]}
    assert "Atorvastatin" in regulated_names
    assert "Metformin" in regulated_names
    assert all(r["intervention_name"] not in regulated_names for r in tiers["top_considerations"])


def test_additional_category_max_three():
    recommendations = [
        _rec(f"Herb-{i}", category=InterventionCategory.HERB, rank=i + 1, confidence_score=0.5 - i * 0.01)
        for i in range(8)
    ]
    tiers = build_recommendation_tiers(
        recommendations,
        _biomarker_summary(["CRP"]),
        [{"system_code": "inflammation", "system_name": "Inflammation", "signal_level": 2, "drivers": ["CRP"]}],
    )
    botanicals = tiers["additional_by_category"].get("botanicals", {})
    assert len(botanicals.get("items", [])) <= 3
    assert botanicals.get("hidden_count", 0) >= 0


def test_top_biological_problems_for_hba1c_ldl_iron():
    problems = build_top_biological_problems(
        _biomarker_summary(["HbA1c", "LDL Cholesterol", "Iron"]),
        [],
        limit=3,
    )
    titles = [p["title"] for p in problems]
    assert any("Metabolic" in t for t in titles)
    assert any("Cardiovascular" in t for t in titles)
    assert any("Nutrient" in t or "iron" in t.lower() for t in titles)


def test_clinical_executive_summary_mentions_themes():
    tiers = build_recommendation_tiers(
        [_rec("Magnesium"), _rec("Berberine", rank=2)],
        _biomarker_summary(["HbA1c"]),
        [{"system_code": "metabolic_health", "system_name": "Metabolic Health", "signal_level": 2, "drivers": ["HbA1c"]}],
        executive_summary="Your labs show glycemic dysregulation.",
    )
    summary = tiers["clinical_executive_summary"]
    assert "Metabolic" in summary or "metabolic" in summary.lower()
    assert len(summary) <= 1200