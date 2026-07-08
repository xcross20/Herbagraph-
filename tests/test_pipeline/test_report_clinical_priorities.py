"""Unit tests for dual clinical / network leverage rankings."""

import pytest

from app.models.enums import EvidenceLevel, EvidenceTier, InterventionCategory, SafetyRiskLevel
from app.pipeline.report_clinical_priorities import build_dual_clinical_rankings

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


def test_clinical_priorities_rank_iron_above_ldl_for_low_iron_panel():
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
        _rec("Magnesium", rank=1, network_rank_score=0.95, pathways_hit=4, biomarkers_explained=2),
        _rec("Lactoferrin", rank=2, network_rank_score=0.7, pathways_hit=2, biomarkers_explained=1),
        _rec("Berberine", rank=3, network_rank_score=0.88, pathways_hit=3, biomarkers_explained=2),
    ]
    intervention_pathways = {
        "Magnesium": ["INSULIN_PI3K_AKT", "AMPK", "HEPATIC_LIPID"],
        "Lactoferrin": ["IRON_HEPCIDIN", "NUTRIENT_DEFICIENCY"],
        "Berberine": ["INSULIN_PI3K_AKT", "AMPK", "HEPATIC_LIPID"],
    }

    dual = build_dual_clinical_rankings(
        biomarker_summary,
        [],
        pathway_activations,
        recommendations,
        intervention_pathways,
    )

    labels = [p["problem_label"] for p in dual["clinical_priorities"]]
    assert "Iron deficiency biology" in labels[0] or dual["clinical_priorities"][0]["biomarker_name"] == "Iron"
    iron_priority = next(p for p in dual["clinical_priorities"] if p["biomarker_name"] == "Iron")
    assert iron_priority["priority_stars"] >= 4
    assert iron_priority["diagnostic_note"]
    assert iron_priority["diagnostic_next_steps"]
    assert any(item.get("kind") == "test" for item in iron_priority["diagnostic_next_steps"])
    assert iron_priority["potential_interventions"]
    assert all("clinical_tags" in item for item in iron_priority["potential_interventions"])
    assert dual["confidence_if_added"]
    assert dual["confidence_if_added"][0]["is_current"] is True
    assert dual["network_leverage_groups"]
    assert all("clinical_tags" in item for group in dual["network_leverage_groups"] for item in group["interventions"])
    assert dual["ranking_questions"]["clinical_priorities"]