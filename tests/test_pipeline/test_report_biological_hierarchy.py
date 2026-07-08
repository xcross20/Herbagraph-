"""Unit tests for biology-first hierarchical report model."""

import pytest

from app.models.enums import EvidenceLevel, EvidenceTier, InterventionCategory, SafetyRiskLevel
from app.pipeline.report_biological_hierarchy import (
    biology_first_network_score,
    build_biological_hierarchy,
    evidence_grade_for,
)
from app.pipeline.report_intent import classify_display_intent

pytestmark = pytest.mark.unit


def _rec(name, *, category=InterventionCategory.SUPPLEMENT, rank=1, confidence=0.6):
    return {
        "rank": rank,
        "intervention_name": name,
        "category": category.value,
        "evidence_level": EvidenceLevel.MODERATE.value,
        "evidence_tier": EvidenceTier.ESTABLISHED.value,
        "confidence_score": confidence,
        "safety_risk": SafetyRiskLevel.LOW.value,
        "is_regulated": False,
        "mechanism": "Test",
    }


def test_evidence_grade_mapping():
    rec = {
        "evidence_tier": EvidenceTier.ESTABLISHED.value,
        "evidence_level": EvidenceLevel.HIGH.value,
    }
    assert evidence_grade_for(rec) == "A+"


def test_biology_first_prefers_multi_pathway_over_single_popular():
    pathway_activations = [
        {
            "pathway_code": "HEPATIC_LIPID",
            "pathway_name": "Hepatic Lipid Metabolism",
            "activation_score": 0.9,
            "contributing_biomarkers": ["LDL Cholesterol"],
        },
        {
            "pathway_code": "AMPK",
            "pathway_name": "AMPK Energy Sensing",
            "activation_score": 0.75,
            "contributing_biomarkers": ["HbA1c"],
        },
    ]
    intervention_pathways = {
        "Berberine": ["HEPATIC_LIPID", "AMPK", "INSULIN_PI3K_AKT", "GLP1_INCRETINS"],
        "Allicin": ["NF_KB"],
        "Anthocyanins": ["NRF2"],
    }
    abnormal = {"LDL Cholesterol", "HbA1c", "Iron"}
    berberine = _rec("Berberine", confidence=0.55)
    allicin = _rec("Allicin", rank=2, confidence=0.85)
    assert biology_first_network_score(
        berberine, intervention_pathways, {p["pathway_code"]: p for p in pathway_activations}, abnormal
    ) > biology_first_network_score(
        allicin, intervention_pathways, {p["pathway_code"]: p for p in pathway_activations}, abnormal
    )


def test_hierarchy_builds_cascade_and_dominant_biology():
    biomarker_summary = {
        "measured_biomarkers": [
            {"biomarker_name": "HbA1c", "status": "high", "value": 6.1},
            {"biomarker_name": "LDL Cholesterol", "status": "high", "value": 140},
            {"biomarker_name": "Iron", "status": "low", "value": 45},
        ]
    }
    pathway_activations = [
        {
            "pathway_code": "HEPATIC_LIPID",
            "pathway_name": "Hepatic Lipid Metabolism",
            "activation_score": 0.93,
            "contributing_biomarkers": ["LDL Cholesterol", "HbA1c"],
            "direction": "activated",
        },
        {
            "pathway_code": "IRON_HEPCIDIN",
            "pathway_name": "Iron/Hepcidin Regulation",
            "activation_score": 0.7,
            "contributing_biomarkers": ["Iron"],
            "direction": "suppressed",
        },
    ]
    biological_systems = [
        {"system_code": "cardiovascular_risk", "system_name": "Cardiovascular Risk", "signal_level": 2, "signal_label": "Moderate Signal", "confidence": "high", "drivers": ["LDL Cholesterol"]},
        {"system_code": "metabolic_health", "system_name": "Metabolic Health", "signal_level": 2, "signal_label": "Moderate Signal", "confidence": "moderate", "drivers": ["HbA1c"]},
    ]
    recommendations = [
        _rec("Berberine"),
        _rec("Exercise", category=InterventionCategory.EXERCISE, rank=2),
        _rec("Atorvastatin", category=InterventionCategory.MEDICATION, rank=3),
    ]
    intervention_pathways = {
        "Berberine": ["HEPATIC_LIPID", "AMPK"],
        "Exercise": ["AMPK", "INSULIN_PI3K_AKT", "HEPATIC_LIPID", "GLP1_INCRETINS", "MTOR_AUTOPHAGY"],
        "Atorvastatin": ["HEPATIC_LIPID"],
    }

    hierarchy = build_biological_hierarchy(
        biomarker_summary,
        biological_systems,
        pathway_activations,
        recommendations,
        intervention_pathways,
    )

    assert hierarchy["cascade"]["abnormal_biomarkers"] == 3
    assert hierarchy["cascade"]["interventions_mapped"] == 3
    assert hierarchy["dominant_biology"]["pathway_code"] == "HEPATIC_LIPID"
    assert hierarchy["dominant_biology"]["confidence_percent"] == 93
    assert "LDL Cholesterol" in hierarchy["dominant_biology"]["affected_biomarkers"]
    assert len(hierarchy["systems_tree"]) >= 1
    assert hierarchy["network_influence_table"][0]["intervention_name"] in {"Exercise", "Berberine"}
    assert classify_display_intent(recommendations[2], {"HbA1c", "LDL Cholesterol", "Iron"}) == "regulated"