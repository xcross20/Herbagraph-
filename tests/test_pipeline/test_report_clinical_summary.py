"""Unit tests for page-1 clinical summary hero."""

import pytest

from app.models.enums import EvidenceLevel, EvidenceTier, InterventionCategory, SafetyRiskLevel
from app.pipeline.report_clinical_priorities import build_dual_clinical_rankings
from app.pipeline.report_clinical_summary import build_clinical_summary_hero

pytestmark = pytest.mark.unit


def _rec(name, *, rank=1, biomarkers_explained=1, pathways_hit=2, network_rank_score=0.5):
    return {
        "rank": rank,
        "intervention_name": name,
        "category": InterventionCategory.SUPPLEMENT.value,
        "evidence_level": EvidenceLevel.HIGH.value,
        "evidence_tier": EvidenceTier.ESTABLISHED.value,
        "confidence_score": 0.9,
        "safety_risk": SafetyRiskLevel.LOW.value,
        "is_regulated": False,
        "network_rank_score": network_rank_score,
        "pathways_hit": pathways_hit,
        "biomarkers_explained": biomarkers_explained,
    }


def _iron_panel_dual():
    biomarker_summary = {
        "measured_biomarkers": [
            {"biomarker_name": "Iron", "status": "low", "value": 45, "reference_range_low": 60, "reference_range_high": 180},
            {"biomarker_name": "HbA1c", "status": "high", "value": 5.9, "reference_range_low": 4.0, "reference_range_high": 5.7},
            {"biomarker_name": "LDL", "status": "high", "value": 109, "reference_range_low": 0, "reference_range_high": 100},
        ]
    }
    pathway_activations = [
        {"pathway_code": "IRON_HEPCIDIN", "pathway_name": "Iron/Hepcidin", "activation_score": 0.85, "contributing_biomarkers": ["Iron"]},
        {"pathway_code": "INSULIN_PI3K_AKT", "pathway_name": "Insulin/PI3K-Akt", "activation_score": 0.9, "contributing_biomarkers": ["HbA1c"]},
        {"pathway_code": "HEPATIC_LIPID", "pathway_name": "Hepatic Lipid", "activation_score": 0.55, "contributing_biomarkers": ["LDL"]},
    ]
    recommendations = [
        _rec("Lactoferrin", rank=1, network_rank_score=0.95, pathways_hit=2, biomarkers_explained=1),
        _rec("Iron", rank=2, network_rank_score=0.7, pathways_hit=2, biomarkers_explained=1),
        _rec("Magnesium", rank=3, network_rank_score=0.88, pathways_hit=3, biomarkers_explained=2),
    ]
    intervention_pathways = {
        "Lactoferrin": ["IRON_HEPCIDIN", "NUTRIENT_DEFICIENCY"],
        "Iron": ["IRON_HEPCIDIN", "NUTRIENT_DEFICIENCY"],
        "Magnesium": ["INSULIN_PI3K_AKT", "AMPK", "HEPATIC_LIPID"],
    }
    dual = build_dual_clinical_rankings(
        biomarker_summary,
        [],
        pathway_activations,
        recommendations,
        intervention_pathways,
    )
    return biomarker_summary, dual


def test_clinical_summary_hero_stitches_primary_finding_and_positioning():
    biomarker_summary, dual = _iron_panel_dual()
    hero = build_clinical_summary_hero(dual, {"confidence_label": "High", "confidence_numeric": 0.92}, biomarker_summary)

    assert hero["model"] == "clinical_summary_hero_v1"
    assert hero["positioning"] == "AI Clinical Reasoning for Precision Nutrition"
    assert hero["title"] == "HerbaGraph Clinical Summary"
    assert hero["overall_confidence_label"] == "HIGH"
    assert hero["overall_confidence_percent"] == 92
    assert "iron" in hero["primary_finding"]["label"].lower()
    assert hero["likely_explanation"]
    assert hero["alternative_explanations"]


def test_clinical_summary_hero_prioritizes_diagnostic_tests_before_interventions():
    biomarker_summary, dual = _iron_panel_dual()
    hero = build_clinical_summary_hero(dual, None, biomarker_summary)

    tests = [t["label"] for t in hero["most_important_next_tests"]]
    assert tests
    assert "Ferritin" in tests[0] or tests[0] in {"Ferritin", "Transferrin Saturation", "TIBC", "CRP"}

    leverage_labels = [i["label"] for i in hero["highest_leverage_interventions"]]
    assert leverage_labels
    assert any(name in leverage_labels for name in ("Lactoferrin", "Iron", "Magnesium"))


def test_clinical_summary_hero_includes_confidence_if_added_ladder():
    biomarker_summary, dual = _iron_panel_dual()
    hero = build_clinical_summary_hero(dual, None, biomarker_summary)

    ladder = hero["confidence_if_added"]
    assert ladder
    assert ladder[0]["is_current"] is True
    assert ladder[0]["confidence_percent"] >= 75
    assert any("Add Ferritin" in row["label"] for row in ladder[1:])
    assert ladder[-1]["confidence_percent"] <= 99