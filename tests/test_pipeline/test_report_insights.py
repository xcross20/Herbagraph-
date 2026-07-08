"""Unit tests for clinician-trust report insights."""

import pytest

from app.pipeline.report_insights import (
    build_differential_explanations,
    build_evidence_summary,
    build_missing_information,
    build_overall_confidence_assessment,
    build_patient_evidence_gaps,
    build_report_insights,
    enrich_biological_systems,
)

pytestmark = pytest.mark.unit


def test_enrich_biological_systems_shows_missing_biomarkers():
    systems = [
        {
            "system_code": "inflammation",
            "system_name": "Inflammation",
            "signal_level": 0,
            "signal_label": "No Signal",
            "direction": "none",
            "confidence": "low",
            "drivers": [],
            "pathways": [],
        }
    ]
    measured = {"Iron", "TIBC"}
    enriched = enrich_biological_systems(systems, measured)
    assert enriched[0]["missing_biomarkers"]
    assert "CRP" in enriched[0]["missing_biomarkers"] or "hs-CRP" in enriched[0]["missing_biomarkers"]
    assert enriched[0]["signal_label"] == "Not Assessable"
    assert enriched[0]["assessment_status"] == "not_assessable"
    assert enriched[0]["unavailable_markers"]


def test_evidence_summary_percentages():
    recs = [
        {"evidence_tier": "established"},
        {"evidence_tier": "established"},
        {"evidence_tier": "emerging"},
        {"evidence_tier": "preclinical"},
    ]
    summary = build_evidence_summary(recs)
    assert summary["established_percent"] == 50.0
    assert summary["emerging_percent"] == 25.0
    assert summary["preclinical_percent"] == 25.0


def test_missing_information_suggests_unmeasured_biomarkers():
    biomarker_summary = {
        "measured_biomarkers": [{"biomarker_name": "Iron", "status": "low"}],
    }
    systems = enrich_biological_systems(
        [{"system_code": "nutrient_status", "system_name": "Nutrient Status", "signal_level": 0, "drivers": [], "pathways": []}],
        {"Iron"},
    )
    mi = build_missing_information(biomarker_summary, systems)
    assert "Ferritin" in mi["suggested_biomarkers"] or "Vitamin D, 25-OH" in mi["suggested_biomarkers"]
    assert mi["ranked_biomarkers"]
    assert mi["ranked_biomarkers"][0]["stars"] >= 1


def test_overall_confidence_single_biomarker_reason():
    assessment = build_overall_confidence_assessment(
        {"total_biomarkers": 1, "abnormal_count": 1},
        [{"confidence_score": 0.9, "evidence_tier": "established"}],
    )
    assert assessment["confidence_heading"] == "Report Confidence"
    assert assessment["confidence_label"] in ("High", "Moderate", "Low")
    assert assessment["reason_checks"]
    assert assessment["confidence_drivers"]
    assert any("one biomarker" in r.lower() for r in assessment["reasons"])


def test_differential_explanations_for_low_iron():
    diff = build_differential_explanations(
        {"measured_biomarkers": [{"biomarker_name": "Iron", "status": "low"}]},
        [{"pathway_code": "IRON_HEPCIDIN", "activation_score": 0.8}],
        [{"system_name": "Nutrient Status", "signal_level": 2}],
    )
    assert diff["explanations"]
    assert diff["explanations"][0]["most_likely"]["explanation"] == "Iron deficiency"
    assert diff["explanations"][0]["alternatives"]


def test_patient_evidence_gaps_for_sparse_iron_panel():
    biomarker_summary = {
        "total_biomarkers": 1,
        "measured_biomarkers": [{"biomarker_name": "Iron", "status": "low"}],
    }
    missing = build_missing_information(
        biomarker_summary,
        enrich_biological_systems(
            [{"system_code": "nutrient_status", "system_name": "Nutrient Status", "signal_level": 2, "drivers": ["Iron"]}],
            {"Iron"},
        ),
    )
    overall = build_overall_confidence_assessment(biomarker_summary, [], missing_information=missing)
    gaps = build_patient_evidence_gaps(biomarker_summary, missing, overall, [{"pathway_code": "IRON_HEPCIDIN", "activation_score": 0.7}])
    assert gaps["strengthening_tests"]
    assert "Ferritin" in gaps["strengthening_tests"]


def test_build_report_insights_includes_new_sections():
    insights = build_report_insights(
        {"total_biomarkers": 1, "abnormal_count": 1, "measured_biomarkers": [{"biomarker_name": "Iron", "status": "low"}]},
        [{"system_code": "nutrient_status", "system_name": "Nutrient Status", "signal_level": 2, "drivers": ["Iron"], "direction": "activated", "confidence": "moderate", "pathways": []}],
        [{"pathway_code": "IRON_HEPCIDIN", "pathway_name": "Iron/Hepcidin", "activation_score": 0.8}],
        [{"intervention_name": "Iron", "evidence_tier": "established", "confidence_score": 0.8}],
    )
    assert insights["differential_explanations"]["explanations"]
    assert insights["patient_evidence_gaps"]["certainty_label"]
    assert insights["missing_information"]["ranked_biomarkers"]
    assert insights["report_methodology"]["steps"]


def test_biological_reasoning_visual_chain():
    from app.pipeline.report_insights import build_biological_reasoning_summary

    summary = build_biological_reasoning_summary(
        {"measured_biomarkers": [{"biomarker_name": "Iron", "status": "low"}]},
        [{"system_name": "Nutrient Status", "signal_level": 2}],
        [{"pathway_name": "Iron/Hepcidin Regulation"}],
        [{"intervention_name": "Iron"}],
        {"established_percent": 60},
        {"suggested_biomarkers": ["Ferritin"]},
    )
    assert len(summary["visual_chain"]) == 5
    assert summary["visual_chain"][0]["label"] == "Iron"