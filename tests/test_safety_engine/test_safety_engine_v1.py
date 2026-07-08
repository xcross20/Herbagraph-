"""Safety Engine v1.0 — inform, don't exclude."""

import pytest

from app.models.enums import EvidenceLevel, InterventionCategory, SafetyRiskLevel
from app.safety_engine.engine import evaluate_interventions
from app.safety_engine.medication_catalog import resolve_medication
from app.safety_engine.patient_context import build_patient_context
from app.schemas.pipeline import LLMRecommendation

pytestmark = pytest.mark.unit


def _rec(name: str) -> LLMRecommendation:
    return LLMRecommendation(
        intervention_name=name,
        category=InterventionCategory.HERB,
        mechanism="Test mechanism.",
        evidence_level=EvidenceLevel.MODERATE,
    )


def test_v1_does_not_exclude_pregnancy_contraindications():
    report = evaluate_interventions(
        [_rec("Berberine")],
        health_profile={"known_conditions": ["Pregnancy"], "current_medications": []},
    )
    assert len(report.approved_recommendations) == 1
    assert report.excluded_recommendations == []
    rec = report.approved_recommendations[0]
    assert rec.safety_risk == SafetyRiskLevel.CONTRAINDICATED
    assert rec.safety_profile is not None
    assert rec.safety_profile.requires_prominent_warning is True


def test_warfarin_curcumin_interaction_with_evidence():
    report = evaluate_interventions(
        [_rec("Curcumin")],
        health_profile={"current_medications": ["Warfarin 5mg daily"], "known_conditions": []},
    )
    rec = report.approved_recommendations[0]
    assert rec.safety_risk == SafetyRiskLevel.MODERATE
    assert rec.safety_profile
    assert any(w.warning_type == "interaction" for w in rec.safety_profile.warnings)


def test_liver_lab_abnormal_triggers_organ_caution_for_egcg():
    from app.models.enums import LabResultStatus
    from app.schemas.pipeline import NormalizedLabResult

    labs = [
        NormalizedLabResult(
            biomarker_name="ALT",
            raw_test_name="ALT",
            value=95.0,
            unit="U/L",
            reference_range_low=7.0,
            reference_range_high=56.0,
            status=LabResultStatus.HIGH,
            category="hepatic",
        )
    ]
    report = evaluate_interventions(
        [_rec("EGCG")],
        health_profile={"known_conditions": [], "current_medications": []},
        normalized_labs=labs,
    )
    rec = report.approved_recommendations[0]
    assert rec.safety_profile
    assert rec.safety_profile.organ_cautions


def test_medication_resolver_matches_generic_names():
    assert resolve_medication("warfarin sodium 5mg") == "Warfarin"
    assert resolve_medication("metformin HCL 500mg") == "Metformin"


def test_patient_context_detects_egfr_impairment():
    from app.models.enums import LabResultStatus
    from app.schemas.pipeline import NormalizedLabResult

    ctx = build_patient_context(
        {"known_conditions": [], "current_medications": []},
        normalized_labs=[
            NormalizedLabResult(
                biomarker_name="eGFR",
                raw_test_name="eGFR",
                value=45.0,
                unit="mL/min",
                reference_range_low=60.0,
                reference_range_high=None,
                status=LabResultStatus.LOW,
                category="renal",
            )
        ],
    )
    assert ctx.kidney_impairment is True
    assert ctx.egfr == 45.0