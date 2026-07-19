"""Unit tests for Stage 7: report_generator.score_confidence and generate_report."""

import pytest

from app.models.enums import (
    EvidenceLevel,
    EvidenceTier,
    InterventionCategory,
    LabResultStatus,
    PathwayDirection,
    SafetyRiskLevel,
    StudySource,
    StudyType,
)
from app.pipeline.report_generator import DISCLAIMER, determine_evidence_tier, generate_report, score_confidence
from app.schemas.pipeline import (
    EvidenceSnippet,
    NormalizedLabResult,
    PathwayActivation,
    SafetyReport,
    ScoredRecommendation,
)

pytestmark = pytest.mark.unit


def make_scored_rec(
    name="Curcumin",
    evidence_level=EvidenceLevel.MODERATE,
    safety_risk=SafetyRiskLevel.LOW,
    cited_study_ids=None,
    category=InterventionCategory.HERB,
):
    return ScoredRecommendation(
        intervention_name=name,
        category=category,
        mechanism="Some mechanism.",
        evidence_level=evidence_level,
        cited_study_ids=cited_study_ids or [],
        safety_risk=safety_risk,
    )


def make_evidence(external_id, quality_score, url=None, study_type=StudyType.RCT):
    return EvidenceSnippet(
        source=StudySource.PUBMED,
        external_id=external_id,
        title=f"Study {external_id}",
        year=2020,
        study_type=study_type,
        quality_score=quality_score,
        url=url,
        intervention_name="Curcumin",
    )


def make_lab(name, status, category=None):
    return NormalizedLabResult(
        biomarker_name=name, raw_test_name=name, value=1.0, status=status, category=category
    )


# ---------------------------------------------------------------------------
# score_confidence: hand-computed exact values
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "evidence_level, expected_evidence_component",
    [
        (EvidenceLevel.HIGH, 0.95),
        (EvidenceLevel.MODERATE, 0.65),
        (EvidenceLevel.LOW, 0.35),
        (EvidenceLevel.PRECLINICAL, 0.20),
    ],
)
def test_evidence_strength_component_by_level(evidence_level, expected_evidence_component):
    rec = make_scored_rec(evidence_level=evidence_level, safety_risk=SafetyRiskLevel.LOW)
    score = score_confidence(rec, [], [], {}, 0)
    # study_quality=0, biomarker_relevance=0, pathway_relevance=0, safety deduction=0
    expected = round(0.35 * expected_evidence_component + 0.10 * 1.0, 4)
    assert score == pytest.approx(expected)


@pytest.mark.parametrize(
    "safety_risk, deduction",
    [
        (SafetyRiskLevel.LOW, 0.0),
        (SafetyRiskLevel.MODERATE, 0.40),
        (SafetyRiskLevel.HIGH, 0.75),
        (SafetyRiskLevel.CONTRAINDICATED, 1.00),
    ],
)
def test_safety_deduction_component_by_risk_level(safety_risk, deduction):
    rec = make_scored_rec(evidence_level=EvidenceLevel.HIGH, safety_risk=safety_risk)
    score = score_confidence(rec, [], [], {}, 0)
    expected = round(0.35 * 0.95 + 0.10 * (1 - deduction), 4)
    assert score == pytest.approx(expected)


def test_study_quality_is_zero_when_no_citations():
    rec = make_scored_rec(cited_study_ids=[])
    score = score_confidence(rec, [], [], {}, 0)
    expected = round(0.35 * 0.65 + 0.10 * 1.0, 4)
    assert score == pytest.approx(expected)


def test_study_quality_is_zero_when_cited_ids_do_not_match_any_evidence():
    rec = make_scored_rec(cited_study_ids=["missing-id"])
    evidence = [make_evidence("E1", 0.9)]
    score = score_confidence(rec, evidence, [], {}, 0)
    expected = round(0.35 * 0.65 + 0.10 * 1.0, 4)
    assert score == pytest.approx(expected)


def test_study_quality_is_mean_of_matched_evidence_quality_scores():
    rec = make_scored_rec(cited_study_ids=["E1", "E2"], evidence_level=EvidenceLevel.HIGH)
    evidence = [make_evidence("E1", 0.8), make_evidence("E2", 0.6)]
    score = score_confidence(rec, evidence, [], {}, 0)
    # study_quality = (0.8 + 0.6) / 2 = 0.7
    expected = round(0.35 * 0.95 + 0.25 * 0.7 + 0.10 * 1.0, 4)
    assert score == pytest.approx(expected)


def test_full_formula_hand_computed_case():
    rec = make_scored_rec(
        name="Curcumin",
        evidence_level=EvidenceLevel.MODERATE,
        safety_risk=SafetyRiskLevel.MODERATE,
        cited_study_ids=["E1", "E2"],
    )
    evidence = [make_evidence("E1", 0.8), make_evidence("E2", 0.6)]
    pathway_activations = [
        PathwayActivation(
            pathway_code="NF_KB",
            pathway_name="NF-kB",
            activation_score=0.9,
            direction=PathwayDirection.ACTIVATED,
            contributing_biomarkers=["CRP", "Ferritin"],
        ),
        PathwayActivation(
            pathway_code="HEPATIC_LIPID",
            pathway_name="Hepatic Lipid",
            activation_score=0.5,
            direction=PathwayDirection.ACTIVATED,
            contributing_biomarkers=["LDL"],
        ),
    ]
    intervention_pathways = {"Curcumin": ["NF_KB", "HEPATIC_LIPID"]}
    total_abnormal = 4

    score = score_confidence(rec, evidence, pathway_activations, intervention_pathways, total_abnormal)

    # evidence_strength=0.65, study_quality=0.7, biomarker_relevance=min(3/4,1)=0.75,
    # pathway_relevance=(0.9+0.5)/2=0.7, safety_deduction=0.40
    expected = round(
        0.35 * 0.65 + 0.25 * 0.7 + 0.20 * 0.75 + 0.10 * 0.7 + 0.10 * (1 - 0.40), 4
    )
    assert expected == pytest.approx(0.6825)
    assert score == pytest.approx(expected)


def test_biomarker_relevance_is_zero_when_total_abnormal_is_zero():
    rec = make_scored_rec(evidence_level=EvidenceLevel.HIGH)
    pathway_activations = [
        PathwayActivation(
            pathway_code="NF_KB",
            pathway_name="NF-kB",
            activation_score=0.9,
            direction=PathwayDirection.ACTIVATED,
            contributing_biomarkers=["CRP"],
        )
    ]
    intervention_pathways = {"Curcumin": ["NF_KB"]}
    score = score_confidence(rec, [], pathway_activations, intervention_pathways, 0)
    # biomarker_relevance=0, pathway_relevance=(0.9)/1=0.9
    expected = round(0.35 * 0.95 + 0.10 * 0.9 + 0.10 * 1.0, 4)
    assert score == pytest.approx(expected)


def test_pathway_relevance_is_zero_when_intervention_has_no_mapped_pathways():
    rec = make_scored_rec(evidence_level=EvidenceLevel.HIGH)
    pathway_activations = [
        PathwayActivation(
            pathway_code="NF_KB",
            pathway_name="NF-kB",
            activation_score=0.9,
            direction=PathwayDirection.ACTIVATED,
            contributing_biomarkers=["CRP"],
        )
    ]
    score = score_confidence(rec, [], pathway_activations, {}, 4)
    expected = round(0.35 * 0.95 + 0.10 * 1.0, 4)
    assert score == pytest.approx(expected)


def test_score_confidence_stays_within_zero_to_one_bounds():
    rec = make_scored_rec(
        evidence_level=EvidenceLevel.HIGH,
        safety_risk=SafetyRiskLevel.LOW,
        cited_study_ids=["E1"],
    )
    evidence = [make_evidence("E1", 1.0)]
    pathway_activations = [
        PathwayActivation(
            pathway_code="NF_KB",
            pathway_name="NF-kB",
            activation_score=1.0,
            direction=PathwayDirection.ACTIVATED,
            contributing_biomarkers=["CRP"],
        )
    ]
    intervention_pathways = {"Curcumin": ["NF_KB"]}
    score = score_confidence(rec, evidence, pathway_activations, intervention_pathways, 1)
    assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


def _base_safety_report(recs):
    return SafetyReport(approved_recommendations=recs, excluded_recommendations=[])


def test_generate_report_ranks_by_confidence_descending():
    high = make_scored_rec(
        name="HighConf",
        evidence_level=EvidenceLevel.HIGH,
        safety_risk=SafetyRiskLevel.LOW,
        cited_study_ids=["MA1", "RCT1"],
    )
    low = make_scored_rec(
        name="LowConf",
        evidence_level=EvidenceLevel.PRECLINICAL,
        safety_risk=SafetyRiskLevel.HIGH,
        cited_study_ids=["PRE1"],
    )
    mid = make_scored_rec(
        name="MidConf",
        evidence_level=EvidenceLevel.MODERATE,
        safety_risk=SafetyRiskLevel.LOW,
        cited_study_ids=["RCT2"],
    )
    evidence = [
        make_evidence("MA1", 0.9, study_type=StudyType.META_ANALYSIS),
        make_evidence("RCT1", 0.8, study_type=StudyType.RCT),
        make_evidence("RCT2", 0.6, study_type=StudyType.RCT),
        make_evidence("PRE1", 0.2, study_type=StudyType.PRECLINICAL),
    ]
    for snippet in evidence:
        snippet.intervention_name = "HighConf" if snippet.external_id in ("MA1", "RCT1") else (
            "MidConf" if snippet.external_id == "RCT2" else "LowConf"
        )

    safety_report = _base_safety_report([low, high, mid])
    report = generate_report(
        normalized_labs=[],
        pathway_activations=[],
        evidence_snippets=evidence,
        safety_report=safety_report,
        biomarker_pattern_analysis="",
        clinician_questions=[],
        intervention_pathways={},
    )

    names_in_order = [r["intervention_name"] for r in report["recommendations"]]
    assert names_in_order[0] == "HighConf"
    assert names_in_order[-1] == "LowConf"
    ranks = [r["rank"] for r in report["recommendations"]]
    assert ranks == [1, 2, 3]


def test_generate_report_overall_confidence_is_mean_of_recommendation_scores():
    rec_a = make_scored_rec(name="A", evidence_level=EvidenceLevel.HIGH, safety_risk=SafetyRiskLevel.LOW)
    rec_b = make_scored_rec(name="B", evidence_level=EvidenceLevel.PRECLINICAL, safety_risk=SafetyRiskLevel.LOW)

    safety_report = _base_safety_report([rec_a, rec_b])
    report = generate_report(
        normalized_labs=[],
        pathway_activations=[],
        evidence_snippets=[],
        safety_report=safety_report,
        biomarker_pattern_analysis="",
        clinician_questions=[],
        intervention_pathways={},
    )

    scores = [r["confidence_score"] for r in report["recommendations"]]
    expected_mean = round(sum(scores) / len(scores), 4)
    assert report["overall_confidence"] == pytest.approx(expected_mean)


def test_generate_report_overall_confidence_zero_when_no_recommendations():
    safety_report = _base_safety_report([])
    report = generate_report(
        normalized_labs=[],
        pathway_activations=[],
        evidence_snippets=[],
        safety_report=safety_report,
        biomarker_pattern_analysis="",
        clinician_questions=[],
        intervention_pathways={},
    )
    assert report["overall_confidence"] == 0.0
    assert report["recommendations"] == []


def test_generate_report_dedupes_citations_by_id():
    rec_a = make_scored_rec(name="A", cited_study_ids=["E1"])
    rec_b = make_scored_rec(name="B", cited_study_ids=["E1", "E2"])
    evidence = [make_evidence("E1", 0.9), make_evidence("E2", 0.5)]

    safety_report = _base_safety_report([rec_a, rec_b])
    report = generate_report(
        normalized_labs=[],
        pathway_activations=[],
        evidence_snippets=evidence,
        safety_report=safety_report,
        biomarker_pattern_analysis="",
        clinician_questions=[],
        intervention_pathways={},
    )

    citation_ids = [c["id"] for c in report["citations"]]
    assert citation_ids.count("E1") == 1
    assert set(citation_ids) == {"E1", "E2"}


def test_generate_report_attaches_food_sources_for_known_compound():
    rec = make_scored_rec(name="Sulforaphane", category=InterventionCategory.PHYTOCHEMICAL)
    safety_report = _base_safety_report([rec])
    report = generate_report(
        normalized_labs=[],
        pathway_activations=[],
        evidence_snippets=[],
        safety_report=safety_report,
        biomarker_pattern_analysis="",
        clinician_questions=[],
        intervention_pathways={},
    )
    food_sources = report["recommendations"][0]["food_sources"]
    assert food_sources is not None
    assert len(food_sources) >= 4


def test_generate_report_food_sources_none_for_unmapped_compound():
    rec = make_scored_rec(name="Boswellia serrata", category=InterventionCategory.HERB)
    safety_report = _base_safety_report([rec])
    report = generate_report(
        normalized_labs=[],
        pathway_activations=[],
        evidence_snippets=[],
        safety_report=safety_report,
        biomarker_pattern_analysis="",
        clinician_questions=[],
        intervention_pathways={},
    )
    assert report["recommendations"][0]["food_sources"] is None


def test_biomarker_summary_counts_total_abnormal_normal_and_categories():
    labs = [
        make_lab("CRP", LabResultStatus.HIGH, category="inflammation"),
        make_lab("LDL", LabResultStatus.HIGH, category="lipids"),
        make_lab("HDL", LabResultStatus.LOW, category="lipids"),
        make_lab("Glucose", LabResultStatus.NORMAL, category="metabolic"),
        make_lab("Vitamin D", LabResultStatus.OPTIMAL, category="vitamins"),
    ]
    safety_report = _base_safety_report([])
    report = generate_report(
        normalized_labs=labs,
        pathway_activations=[],
        evidence_snippets=[],
        safety_report=safety_report,
        biomarker_pattern_analysis="",
        clinician_questions=[],
        intervention_pathways={},
    )
    summary = report["biomarker_summary"]
    assert summary["total_biomarkers"] == 5
    assert summary["abnormal_count"] == 3
    assert summary["normal_count"] == 2
    assert summary["categories_affected"] == {"inflammation": 1, "lipids": 2}


def test_executive_summary_prefers_provided_pattern_analysis():
    safety_report = _base_safety_report([])
    report = generate_report(
        normalized_labs=[],
        pathway_activations=[],
        evidence_snippets=[],
        safety_report=safety_report,
        biomarker_pattern_analysis="Custom LLM-authored narrative.",
        clinician_questions=[],
        intervention_pathways={},
    )
    assert report["executive_summary"] == "Custom LLM-authored narrative."


def test_executive_summary_fallback_when_no_abnormal_biomarkers():
    labs = [make_lab("CRP", LabResultStatus.NORMAL)]
    safety_report = _base_safety_report([])
    report = generate_report(
        normalized_labs=labs,
        pathway_activations=[],
        evidence_snippets=[],
        safety_report=safety_report,
        biomarker_pattern_analysis="",
        clinician_questions=[],
        intervention_pathways={},
    )
    assert "within reference ranges" in report["executive_summary"]


def test_executive_summary_fallback_when_abnormal_biomarkers_present():
    labs = [
        make_lab("CRP", LabResultStatus.HIGH),
        make_lab("Glucose", LabResultStatus.NORMAL),
    ]
    safety_report = _base_safety_report([])
    report = generate_report(
        normalized_labs=labs,
        pathway_activations=[],
        evidence_snippets=[],
        safety_report=safety_report,
        biomarker_pattern_analysis="",
        clinician_questions=[],
        intervention_pathways={},
    )
    assert report["executive_summary"] == (
        "Your labs show 1 of 2 biomarkers outside their reference range, "
        "implicating one or more biological pathways addressed below."
    )


def test_disclaimer_always_present_and_contains_disclaimer_keyword():
    safety_report = _base_safety_report([])
    report = generate_report(
        normalized_labs=[],
        pathway_activations=[],
        evidence_snippets=[],
        safety_report=safety_report,
        biomarker_pattern_analysis="",
        clinician_questions=[],
        intervention_pathways={},
    )
    assert report["disclaimer"] == DISCLAIMER
    assert "does not diagnose" in report["disclaimer"].lower()
    assert "healthcare provider" in report["disclaimer"].lower()


def test_safety_summary_reflects_high_risk_and_review_flag():
    rec = make_scored_rec(name="Berberine", safety_risk=SafetyRiskLevel.HIGH)
    safety_report = SafetyReport(
        approved_recommendations=[rec],
        excluded_recommendations=[],
        requires_clinician_review=True,
        overall_note="One or more recommendations require clinician review before starting.",
    )
    report = generate_report(
        normalized_labs=[],
        pathway_activations=[],
        evidence_snippets=[],
        safety_report=safety_report,
        biomarker_pattern_analysis="",
        clinician_questions=[],
        intervention_pathways={},
    )
    assert report["safety_summary"]["requires_clinician_review"] is True
    assert "Berberine" in report["safety_summary"]["high_risk_interventions"]


def test_clinician_questions_passed_through_unmodified():
    safety_report = _base_safety_report([])
    questions = ["Should I discuss statins with my doctor?"]
    report = generate_report(
        normalized_labs=[],
        pathway_activations=[],
        evidence_snippets=[],
        safety_report=safety_report,
        biomarker_pattern_analysis="",
        clinician_questions=questions,
        intervention_pathways={},
    )
    assert report["clinician_questions"] == questions


# ---------------------------------------------------------------------------
# determine_evidence_tier
# ---------------------------------------------------------------------------


def test_evidence_tier_established_for_meta_analysis():
    rec = make_scored_rec(cited_study_ids=["S1"])
    evidence_by_id = {"S1": make_evidence("S1", 1.0, study_type=StudyType.META_ANALYSIS)}
    assert determine_evidence_tier(rec, evidence_by_id) == EvidenceTier.ESTABLISHED


def test_evidence_tier_established_for_systematic_review():
    rec = make_scored_rec(cited_study_ids=["S1"])
    evidence_by_id = {"S1": make_evidence("S1", 0.9, study_type=StudyType.SYSTEMATIC_REVIEW)}
    assert determine_evidence_tier(rec, evidence_by_id) == EvidenceTier.ESTABLISHED


def test_evidence_tier_established_for_multiple_rcts():
    rec = make_scored_rec(cited_study_ids=["S1", "S2"])
    evidence_by_id = {
        "S1": make_evidence("S1", 0.85, study_type=StudyType.RCT),
        "S2": make_evidence("S2", 0.85, study_type=StudyType.RCT),
    }
    assert determine_evidence_tier(rec, evidence_by_id) == EvidenceTier.ESTABLISHED


def test_evidence_tier_emerging_for_single_rct():
    rec = make_scored_rec(cited_study_ids=["S1"])
    evidence_by_id = {"S1": make_evidence("S1", 0.85, study_type=StudyType.RCT)}
    assert determine_evidence_tier(rec, evidence_by_id) == EvidenceTier.EMERGING


def test_evidence_tier_emerging_for_cohort_study():
    rec = make_scored_rec(cited_study_ids=["S1"])
    evidence_by_id = {"S1": make_evidence("S1", 0.6, study_type=StudyType.COHORT)}
    assert determine_evidence_tier(rec, evidence_by_id) == EvidenceTier.EMERGING


def test_evidence_tier_emerging_for_case_control():
    rec = make_scored_rec(cited_study_ids=["S1"])
    evidence_by_id = {"S1": make_evidence("S1", 0.45, study_type=StudyType.CASE_CONTROL)}
    assert determine_evidence_tier(rec, evidence_by_id) == EvidenceTier.EMERGING


def test_evidence_tier_preclinical_when_only_preclinical_cited():
    rec = make_scored_rec(cited_study_ids=["S1"])
    evidence_by_id = {"S1": make_evidence("S1", 0.2, study_type=StudyType.PRECLINICAL)}
    assert determine_evidence_tier(rec, evidence_by_id) == EvidenceTier.PRECLINICAL


def test_evidence_tier_research_hypothesis_when_no_citations_resolve():
    rec = make_scored_rec(cited_study_ids=["UNKNOWN"])
    assert determine_evidence_tier(rec, {}) == EvidenceTier.RESEARCH_HYPOTHESIS


def test_generate_report_attaches_evidence_tier_and_label():
    rec = make_scored_rec(cited_study_ids=["S1"], evidence_level=EvidenceLevel.HIGH)
    evidence = [make_evidence("S1", 1.0, study_type=StudyType.META_ANALYSIS)]
    safety_report = _base_safety_report([rec])
    report = generate_report(
        normalized_labs=[],
        pathway_activations=[],
        evidence_snippets=evidence,
        safety_report=safety_report,
        biomarker_pattern_analysis="",
        clinician_questions=[],
        intervention_pathways={},
    )
    scored = report["recommendations"][0]
    assert scored["evidence_tier"] == "established"
    assert scored["evidence_tier_label"] == "Established Evidence"


# ---------------------------------------------------------------------------
# biomarker_interpretations
# ---------------------------------------------------------------------------


def test_biomarker_interpretations_only_include_abnormal_biomarkers():
    labs = [
        NormalizedLabResult(
            biomarker_name="CRP", raw_test_name="CRP", value=8.2, unit="mg/L",
            status=LabResultStatus.HIGH, category="inflammatory",
        ),
        NormalizedLabResult(
            biomarker_name="Glucose", raw_test_name="Glucose", value=85, unit="mg/dL",
            status=LabResultStatus.OPTIMAL, category="metabolic",
        ),
    ]
    safety_report = _base_safety_report([])
    report = generate_report(
        normalized_labs=labs,
        pathway_activations=[],
        evidence_snippets=[],
        safety_report=safety_report,
        biomarker_pattern_analysis="",
        clinician_questions=[],
        intervention_pathways={},
    )
    interpretations = report["biomarker_interpretations"]
    assert len(interpretations) == 1
    assert interpretations[0]["biomarker_name"] == "CRP"
    assert interpretations[0]["status"] == "high"
    assert "CRP" in interpretations[0]["interpretation"]
    assert "8.2" in interpretations[0]["interpretation"]


def test_biomarker_interpretations_empty_when_all_normal():
    labs = [
        NormalizedLabResult(
            biomarker_name="Glucose", raw_test_name="Glucose", value=85, unit="mg/dL",
            status=LabResultStatus.NORMAL, category="metabolic",
        ),
    ]
    safety_report = _base_safety_report([])
    report = generate_report(
        normalized_labs=labs,
        pathway_activations=[],
        evidence_snippets=[],
        safety_report=safety_report,
        biomarker_pattern_analysis="",
        clinician_questions=[],
        intervention_pathways={},
    )
    assert report["biomarker_interpretations"] == []


def test_disclaimer_mentions_discussion_not_replacement():
    assert "discussion" in DISCLAIMER.lower()
    assert "does not diagnose disease" in DISCLAIMER.lower()
    assert "replace licensed medical judgment" in DISCLAIMER.lower()


def test_generate_report_includes_biological_systems():
    safety_report = _base_safety_report([])
    pathway_activations = [
        PathwayActivation(
            pathway_code="NF_KB",
            pathway_name="NF-kB",
            activation_score=0.9,
            direction=PathwayDirection.ACTIVATED,
            contributing_biomarkers=["CRP"],
        )
    ]
    report = generate_report(
        normalized_labs=[],
        pathway_activations=pathway_activations,
        evidence_snippets=[],
        safety_report=safety_report,
        biomarker_pattern_analysis="",
        clinician_questions=[],
        intervention_pathways={},
    )
    systems = report["biological_systems"]
    assert len(systems) == 7
    inflammation = next(s for s in systems if s["system_code"] == "inflammation")
    assert inflammation["signal_level"] == 3
    assert inflammation["drivers"] == ["CRP"]
