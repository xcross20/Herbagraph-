"""Four-score decomposition: scores must be independent and not chase 90%."""

from app.evidence_confidence.decomposition import decompose_confidence
from app.evidence_confidence.engine import explain_recommendation
from app.models.enums import EvidenceLevel, InterventionCategory, LabResultStatus, StudySource, StudyType
from app.schemas.pipeline import EvidenceSnippet, LLMRecommendation, NormalizedLabResult, PathwayActivation


def _b12_rec() -> LLMRecommendation:
    return LLMRecommendation(
        intervention_name="Vitamin B12",
        category=InterventionCategory.SUPPLEMENT,
        mechanism="Cofactor for methionine synthase and methylmalonyl-CoA mutase.",
        evidence_level=EvidenceLevel.MODERATE,
        cited_study_ids=["pm-b12"],
        typical_dose="1000 mcg daily",
    )


def _rct(external_id: str = "pm-b12") -> EvidenceSnippet:
    return EvidenceSnippet(
        source=StudySource.PUBMED,
        external_id=external_id,
        title="B12 repletion in deficiency",
        year=2022,
        study_type=StudyType.RCT,
        quality_score=0.8,
        intervention_name="Vitamin B12",
        abstract_snippet="Randomized trial showed improved MMA and neurologic scores.",
    )


def test_strong_evidence_empty_context_scores_diverge():
    result = decompose_confidence(
        evidence_numeric=0.88,
        contradiction_penalty=0.0,
        supporting_biomarker_names=["Vitamin B12", "MCV"],
        present_lab_names=["Vitamin B12", "MCV"],
        pathway_codes={"NUTRIENT_DEFICIENCY", "ONE_CARBON_METHYLATION"},
        intervention_name="Vitamin B12",
        health_profile={},
        has_safety_data=True,
        has_mechanism=True,
        cited_human_studies=3,
    )
    assert result.evidence_confidence.score == 0.88
    assert result.data_sufficiency.score < result.evidence_confidence.score - 0.10
    assert result.decision_confidence.score != result.evidence_confidence.score
    assert result.decision_confidence.score != result.data_sufficiency.score
    assert "MMA" in result.missing_biomarkers
    assert "Homocysteine" in result.missing_biomarkers
    assert result.primary_bottleneck in {"patient_context", "biomarker_incompleteness"}
    assert any("MMA" in item.action or "Homocysteine" in item.action for item in result.gap_analysis)


def test_full_context_raises_sufficiency_not_evidence():
    empty = decompose_confidence(
        evidence_numeric=0.72,
        contradiction_penalty=0.0,
        supporting_biomarker_names=["Vitamin B12"],
        present_lab_names=["Vitamin B12"],
        pathway_codes={"ONE_CARBON_METHYLATION"},
        intervention_name="Vitamin B12",
        health_profile={},
        has_safety_data=True,
        has_mechanism=True,
        cited_human_studies=2,
    )
    full = decompose_confidence(
        evidence_numeric=0.72,
        contradiction_penalty=0.0,
        supporting_biomarker_names=["Vitamin B12"],
        present_lab_names=["Vitamin B12", "MMA", "Homocysteine", "MCV", "Folate"],
        pathway_codes={"ONE_CARBON_METHYLATION"},
        intervention_name="Vitamin B12",
        health_profile={
            "age_range": "50-59",
            "biological_sex": "female",
            "current_medications": ["metformin"],
            "known_conditions": ["neuropathy"],
            "current_supplements": [],
            "health_goals": ["energy"],
        },
        has_safety_data=True,
        has_mechanism=True,
        cited_human_studies=2,
    )
    assert empty.evidence_confidence.score == full.evidence_confidence.score
    assert full.data_sufficiency.score > empty.data_sufficiency.score
    assert full.patient_match.score > empty.patient_match.score


def test_stop_band_clears_gap_list_no_ninety_percent_hunt():
    result = decompose_confidence(
        evidence_numeric=0.40,
        contradiction_penalty=0.10,
        supporting_biomarker_names=["CRP"],
        present_lab_names=["CRP", "hs-CRP", "ESR", "Glucose", "Insulin", "HbA1c"],
        pathway_codes={"NF_KB"},
        intervention_name="Curcumin",
        health_profile={
            "age_range": "40-49",
            "biological_sex": "male",
            "current_medications": ["none"],
            "known_conditions": ["none listed"],
            "current_supplements": ["none"],
            "health_goals": ["inflammation"],
        },
        has_safety_data=True,
        has_mechanism=True,
        cited_human_studies=1,
    )
    if result.decision_band == "stop":
        assert result.gap_analysis == []
    assert result.decision_band in {"action", "investigate", "stop"}
    advertised = sum(item.expected_gain for item in result.gap_analysis)
    assert advertised <= 0.18 + 1e-9


def test_explain_recommendation_includes_decomposition():
    rec = _b12_rec()
    labs = [
        NormalizedLabResult(
            biomarker_name="Vitamin B12",
            raw_test_name="B12",
            value=210,
            unit="pg/mL",
            status=LabResultStatus.LOW,
            category="nutritional",
        ),
        NormalizedLabResult(
            biomarker_name="MCV",
            raw_test_name="MCV",
            value=104,
            unit="fL",
            status=LabResultStatus.HIGH,
            category="cbc",
        ),
    ]
    result = explain_recommendation(
        rec,
        [_rct()],
        [
            PathwayActivation(
                pathway_code="NUTRIENT_DEFICIENCY",
                pathway_name="Nutrient Deficiency",
                activation_score=0.8,
                direction="suppressed",
                contributing_biomarkers=["Vitamin B12"],
            )
        ],
        {"Vitamin B12": ["NUTRIENT_DEFICIENCY", "ONE_CARBON_METHYLATION"]},
        labs,
        {},
    )
    decomp = result.confidence_decomposition
    assert decomp is not None
    assert decomp.formula_version == "decomposition_v1"
    assert decomp.evidence_confidence.percent == int(round(result.evidence_confidence_numeric * 100))
    assert decomp.data_sufficiency.score < 0.85
    assert decomp.decision_band in {"action", "investigate", "stop"}
