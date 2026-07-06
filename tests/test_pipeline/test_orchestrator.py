"""Unit tests for the full pipeline orchestrator (app.pipeline.orchestrator.run_pipeline).

Stage 4 (retrieve_evidence) and Stage 5 (generate_reasoning) are mocked at the
module level so these tests exercise the real parsing/normalization/pathway-mapping/
safety/report-generation stages against canned evidence + reasoning output, without
any network or LLM calls.
"""

from unittest.mock import AsyncMock

import pytest

from app.models.enums import EvidenceLevel, InterventionCategory, StudySource, StudyType
from app.pipeline import orchestrator
from app.schemas.pipeline import EvidenceSnippet, LLMRecommendation, LLMReasoningOutput

pytestmark = pytest.mark.unit

RAW_TEXT = """\
CRP                    8.20  mg/L   (0.00-3.00)
Glucose                85    mg/dL  (70-99)
"""


def canned_evidence():
    return [
        EvidenceSnippet(
            source=StudySource.PUBMED,
            external_id="PMID:12345",
            title="Curcumin reduces CRP in metabolic syndrome",
            year=2019,
            study_type=StudyType.RCT,
            quality_score=0.85,
            url="https://pubmed.ncbi.nlm.nih.gov/12345",
            abstract_snippet="A randomized trial of curcumin.",
            intervention_name="Curcumin",
        )
    ]


def canned_reasoning():
    return LLMReasoningOutput(
        biomarker_pattern_analysis="Elevated CRP indicates NF-kB pathway activation.",
        pathway_summaries=["NF-kB signaling is upregulated."],
        recommendations=[
            LLMRecommendation(
                intervention_name="Curcumin",
                category=InterventionCategory.HERB,
                mechanism="Inhibits NF-kB signaling.",
                evidence_level=EvidenceLevel.MODERATE,
                typical_dose="500mg BID",
                cited_study_ids=["PMID:12345"],
                rationale="Supported by RCT evidence.",
            )
        ],
        clinician_questions=["Any history of GI sensitivity?"],
    )


@pytest.fixture(autouse=True)
def mock_stage4_and_stage5(monkeypatch):
    """Patch retrieve_evidence and generate_reasoning at the orchestrator module level
    so tests never touch the network or an LLM, while the rest of the pipeline (parsing,
    normalization, pathway mapping, safety, report generation) runs for real."""
    retrieve_evidence_mock = AsyncMock(return_value=canned_evidence())
    generate_reasoning_mock = AsyncMock(return_value=canned_reasoning())
    monkeypatch.setattr(orchestrator, "retrieve_evidence", retrieve_evidence_mock)
    monkeypatch.setattr(orchestrator, "generate_reasoning", generate_reasoning_mock)
    return {"retrieve_evidence": retrieve_evidence_mock, "generate_reasoning": generate_reasoning_mock}


HEALTH_PROFILE = {"age": 42, "sex": "female", "known_conditions": [], "current_medications": []}


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


async def test_run_pipeline_raises_valueerror_when_neither_source_provided():
    with pytest.raises(ValueError):
        await orchestrator.run_pipeline(health_profile=HEALTH_PROFILE)


async def test_run_pipeline_valueerror_when_only_filename_given_without_bytes():
    with pytest.raises(ValueError):
        await orchestrator.run_pipeline(filename="labs.txt", health_profile=HEALTH_PROFILE)


async def test_run_pipeline_valueerror_when_only_file_bytes_given_without_filename():
    with pytest.raises(ValueError):
        await orchestrator.run_pipeline(file_bytes=RAW_TEXT.encode(), health_profile=HEALTH_PROFILE)


# ---------------------------------------------------------------------------
# raw_text path: end-to-end shape of the returned report
# ---------------------------------------------------------------------------


async def test_run_pipeline_with_raw_text_returns_dict():
    result = await orchestrator.run_pipeline(raw_text=RAW_TEXT, health_profile=HEALTH_PROFILE)
    assert isinstance(result, dict)


async def test_run_pipeline_with_raw_text_has_expected_top_level_keys():
    result = await orchestrator.run_pipeline(raw_text=RAW_TEXT, health_profile=HEALTH_PROFILE)
    expected_keys = {
        "overall_confidence",
        "recommendations",
        "biomarker_summary",
        "pathway_activations",
        "citations",
        "disclaimer",
        "safety_summary",
        "clinician_questions",
    }
    assert expected_keys.issubset(result.keys())


async def test_run_pipeline_biomarker_summary_reflects_parsed_labs():
    result = await orchestrator.run_pipeline(raw_text=RAW_TEXT, health_profile=HEALTH_PROFILE)
    # CRP is HIGH (8.2 > 3.0), Glucose 85 falls in the optimal 70-85 band -> not abnormal.
    assert result["biomarker_summary"]["total_biomarkers"] == 2
    assert result["biomarker_summary"]["abnormal_count"] == 1


async def test_run_pipeline_pathway_activations_include_nf_kb():
    result = await orchestrator.run_pipeline(raw_text=RAW_TEXT, health_profile=HEALTH_PROFILE)
    codes = {p["pathway_code"] for p in result["pathway_activations"]}
    assert "NF_KB" in codes


async def test_run_pipeline_recommendations_include_curcumin_with_confidence_score():
    result = await orchestrator.run_pipeline(raw_text=RAW_TEXT, health_profile=HEALTH_PROFILE)
    assert len(result["recommendations"]) == 1
    rec = result["recommendations"][0]
    assert rec["intervention_name"] == "Curcumin"
    assert rec["confidence_score"] is not None
    assert rec["rank"] == 1


async def test_run_pipeline_citations_include_cited_evidence():
    result = await orchestrator.run_pipeline(raw_text=RAW_TEXT, health_profile=HEALTH_PROFILE)
    citation_ids = {c["id"] for c in result["citations"]}
    assert citation_ids == {"PMID:12345"}


async def test_run_pipeline_clinician_questions_pass_through():
    result = await orchestrator.run_pipeline(raw_text=RAW_TEXT, health_profile=HEALTH_PROFILE)
    assert result["clinician_questions"] == ["Any history of GI sensitivity?"]


async def test_run_pipeline_disclaimer_present():
    result = await orchestrator.run_pipeline(raw_text=RAW_TEXT, health_profile=HEALTH_PROFILE)
    assert "not a medical" in result["disclaimer"].lower() or "disclaimer" in result["disclaimer"].lower()


async def test_run_pipeline_safety_summary_shape():
    result = await orchestrator.run_pipeline(raw_text=RAW_TEXT, health_profile=HEALTH_PROFILE)
    assert "overall_note" in result["safety_summary"]
    assert "requires_clinician_review" in result["safety_summary"]
    assert "high_risk_interventions" in result["safety_summary"]


async def test_run_pipeline_overall_confidence_is_between_0_and_1():
    result = await orchestrator.run_pipeline(raw_text=RAW_TEXT, health_profile=HEALTH_PROFILE)
    assert 0.0 <= result["overall_confidence"] <= 1.0


# ---------------------------------------------------------------------------
# file_bytes + filename path
# ---------------------------------------------------------------------------


async def test_run_pipeline_with_file_bytes_and_txt_filename():
    result = await orchestrator.run_pipeline(
        file_bytes=RAW_TEXT.encode("utf-8"), filename="labs.txt", health_profile=HEALTH_PROFILE
    )
    assert result["biomarker_summary"]["total_biomarkers"] == 2
    assert result["recommendations"][0]["intervention_name"] == "Curcumin"


async def test_run_pipeline_raw_text_takes_precedence_over_file_bytes():
    # raw_text is checked first in run_pipeline, so when both are provided the
    # file_bytes/filename branch is never reached.
    result = await orchestrator.run_pipeline(
        raw_text=RAW_TEXT,
        file_bytes=b"garbage not lab data",
        filename="labs.txt",
        health_profile=HEALTH_PROFILE,
    )
    assert result["biomarker_summary"]["total_biomarkers"] == 2


# ---------------------------------------------------------------------------
# Stage wiring: verify mocked stages receive the right arguments
# ---------------------------------------------------------------------------


async def test_run_pipeline_calls_retrieve_evidence_with_pathway_activations(mock_stage4_and_stage5):
    await orchestrator.run_pipeline(raw_text=RAW_TEXT, health_profile=HEALTH_PROFILE)
    mock_stage4_and_stage5["retrieve_evidence"].assert_awaited_once()
    args, kwargs = mock_stage4_and_stage5["retrieve_evidence"].call_args
    pathway_activations = args[0] if args else kwargs["pathway_activations"]
    assert any(p.pathway_code == "NF_KB" for p in pathway_activations)


async def test_run_pipeline_calls_generate_reasoning_with_expected_args(mock_stage4_and_stage5):
    await orchestrator.run_pipeline(raw_text=RAW_TEXT, health_profile=HEALTH_PROFILE)
    mock_stage4_and_stage5["generate_reasoning"].assert_awaited_once()
    _, kwargs = mock_stage4_and_stage5["generate_reasoning"].call_args
    call_args = mock_stage4_and_stage5["generate_reasoning"].call_args
    positional = call_args.args
    all_args = list(positional) + list(kwargs.values())
    # health_profile dict should have been forwarded somewhere in the call
    assert HEALTH_PROFILE in all_args or kwargs.get("health_profile") == HEALTH_PROFILE


async def test_run_pipeline_generate_reasoning_receives_evidence_from_retrieve_evidence(
    mock_stage4_and_stage5,
):
    await orchestrator.run_pipeline(raw_text=RAW_TEXT, health_profile=HEALTH_PROFILE)
    call = mock_stage4_and_stage5["generate_reasoning"].call_args
    all_values = list(call.args) + list(call.kwargs.values())
    evidence_arg = next((v for v in all_values if isinstance(v, list) and v and isinstance(v[0], EvidenceSnippet)), None)
    assert evidence_arg is not None
    assert evidence_arg[0].external_id == "PMID:12345"


# ---------------------------------------------------------------------------
# Edge case: no abnormal biomarkers still produces a valid report
# ---------------------------------------------------------------------------


async def test_run_pipeline_with_all_normal_labs_still_returns_valid_report():
    normal_text = "Glucose                85    mg/dL  (70-99)\n"
    result = await orchestrator.run_pipeline(raw_text=normal_text, health_profile=HEALTH_PROFILE)
    assert result["biomarker_summary"]["abnormal_count"] == 0
    assert result["pathway_activations"] == []
    # generate_reasoning is still mocked to return the canned recommendation,
    # regardless of pathway activations, since Stage 4/5 are mocked out.
    assert isinstance(result["recommendations"], list)


async def test_run_pipeline_empty_raw_text_returns_report_with_zero_biomarkers():
    result = await orchestrator.run_pipeline(raw_text="", health_profile=HEALTH_PROFILE)
    assert result["biomarker_summary"]["total_biomarkers"] == 0
    assert result["biomarker_summary"]["abnormal_count"] == 0
