"""Unit tests for Stage 5: llm_reasoner.

Covers parse_llm_response (pure JSON parsing + citation/intervention sanitization)
and generate_reasoning (async orchestration around a mocked AsyncAnthropic client),
including the de-identification of the outbound payload and the empty-evidence
short-circuit that must never call the network.
"""

import json
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from app.models.enums import (
    EvidenceLevel,
    InterventionCategory,
    LabResultStatus,
    PathwayDirection,
    StudySource,
    StudyType,
)
from app.pipeline.llm_reasoner import (
    LLMReasoningError,
    _build_payload,
    _sanitize_recommendations,
    _valid_external_ids,
    generate_reasoning,
    parse_llm_response,
)
from app.schemas.pipeline import EvidenceSnippet, LLMReasoningOutput, NormalizedLabResult, PathwayActivation

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def make_evidence(
    intervention_name="Curcumin",
    external_id="PMID:111",
    source=StudySource.PUBMED,
    title="Curcumin and inflammation",
    quality_score=0.8,
):
    return EvidenceSnippet(
        source=source,
        external_id=external_id,
        title=title,
        year=2020,
        study_type=StudyType.RCT,
        quality_score=quality_score,
        url="https://pubmed.ncbi.nlm.nih.gov/111",
        abstract_snippet="Some abstract.",
        intervention_name=intervention_name,
    )


def make_lab(
    biomarker_name="CRP",
    status=LabResultStatus.HIGH,
    value=8.2,
):
    return NormalizedLabResult(
        biomarker_name=biomarker_name,
        raw_test_name="CRP",
        value=value,
        unit="mg/L",
        reference_range_low=0.0,
        reference_range_high=3.0,
        status=status,
        category="inflammation",
    )


def make_pathway(pathway_code="NF_KB", pathway_name="NF-kB", activation_score=0.7):
    return PathwayActivation(
        pathway_code=pathway_code,
        pathway_name=pathway_name,
        activation_score=activation_score,
        direction=PathwayDirection.ACTIVATED,
        contributing_biomarkers=["CRP"],
    )


def make_raw_recommendation(
    intervention_name="Curcumin",
    cited_study_ids=None,
    category="herb",
    evidence_level="moderate",
):
    return {
        "intervention_name": intervention_name,
        "category": category,
        "mechanism": "Inhibits NF-kB signaling.",
        "evidence_level": evidence_level,
        "typical_dose": "500mg BID",
        "cited_study_ids": cited_study_ids if cited_study_ids is not None else ["PMID:111"],
        "rationale": "Reduces inflammatory markers.",
    }


def make_llm_json(recommendations=None, **overrides):
    body = {
        "biomarker_pattern_analysis": "Elevated CRP suggests systemic inflammation.",
        "pathway_summaries": ["NF-kB pathway is activated."],
        "recommendations": recommendations if recommendations is not None else [make_raw_recommendation()],
        "clinician_questions": ["Any history of GI issues?"],
    }
    body.update(overrides)
    return json.dumps(body)


# ---------------------------------------------------------------------------
# parse_llm_response: valid JSON, well-formed recommendations
# ---------------------------------------------------------------------------


def test_parse_llm_response_returns_llm_reasoning_output():
    evidence = [make_evidence()]
    result = parse_llm_response(make_llm_json(), evidence)
    assert isinstance(result, LLMReasoningOutput)


def test_parse_llm_response_preserves_biomarker_pattern_analysis():
    evidence = [make_evidence()]
    result = parse_llm_response(make_llm_json(), evidence)
    assert result.biomarker_pattern_analysis == "Elevated CRP suggests systemic inflammation."


def test_parse_llm_response_preserves_pathway_summaries():
    evidence = [make_evidence()]
    result = parse_llm_response(make_llm_json(), evidence)
    assert result.pathway_summaries == ["NF-kB pathway is activated."]


def test_parse_llm_response_preserves_clinician_questions():
    evidence = [make_evidence()]
    result = parse_llm_response(make_llm_json(), evidence)
    assert result.clinician_questions == ["Any history of GI issues?"]


def test_parse_llm_response_keeps_valid_recommendation():
    evidence = [make_evidence(intervention_name="Curcumin", external_id="PMID:111")]
    result = parse_llm_response(make_llm_json(), evidence)
    assert len(result.recommendations) == 1
    rec = result.recommendations[0]
    assert rec.intervention_name == "Curcumin"
    assert rec.cited_study_ids == ["PMID:111"]
    assert rec.category == InterventionCategory.HERB
    assert rec.evidence_level == EvidenceLevel.MODERATE


def test_parse_llm_response_missing_top_level_keys_default_gracefully():
    evidence = [make_evidence()]
    raw = json.dumps({})
    result = parse_llm_response(raw, evidence)
    assert result.biomarker_pattern_analysis == ""
    assert result.pathway_summaries == []
    assert result.recommendations == []
    assert result.clinician_questions == []


# ---------------------------------------------------------------------------
# parse_llm_response: malformed JSON
# ---------------------------------------------------------------------------


def test_parse_llm_response_raises_on_malformed_json():
    with pytest.raises(LLMReasoningError):
        parse_llm_response("not json at all {{{", [make_evidence()])


def test_parse_llm_response_raises_on_truncated_json():
    good = make_llm_json()
    truncated = good[: len(good) // 2]
    with pytest.raises(LLMReasoningError):
        parse_llm_response(truncated, [make_evidence()])


def test_parse_llm_response_raises_on_empty_string():
    with pytest.raises(LLMReasoningError):
        parse_llm_response("", [make_evidence()])


def test_parse_llm_response_error_message_mentions_json():
    with pytest.raises(LLMReasoningError, match="valid JSON"):
        parse_llm_response("{bad json", [make_evidence()])


# ---------------------------------------------------------------------------
# parse_llm_response: intervention_name filtering
# ---------------------------------------------------------------------------


def test_recommendation_for_unknown_intervention_is_dropped():
    evidence = [make_evidence(intervention_name="Curcumin", external_id="PMID:111")]
    raw = make_llm_json(recommendations=[make_raw_recommendation(intervention_name="Unicorn Root")])
    result = parse_llm_response(raw, evidence)
    assert result.recommendations == []


def test_recommendation_for_known_intervention_survives():
    evidence = [make_evidence(intervention_name="Curcumin", external_id="PMID:111")]
    raw = make_llm_json(recommendations=[make_raw_recommendation(intervention_name="Curcumin")])
    result = parse_llm_response(raw, evidence)
    assert len(result.recommendations) == 1
    assert result.recommendations[0].intervention_name == "Curcumin"


def test_intervention_name_matching_is_case_sensitive():
    evidence = [make_evidence(intervention_name="Curcumin", external_id="PMID:111")]
    raw = make_llm_json(recommendations=[make_raw_recommendation(intervention_name="curcumin")])
    result = parse_llm_response(raw, evidence)
    assert result.recommendations == []


# ---------------------------------------------------------------------------
# parse_llm_response: citation filtering
# ---------------------------------------------------------------------------


def test_recommendation_with_mixed_valid_invalid_citations_keeps_only_valid():
    evidence = [
        make_evidence(intervention_name="Curcumin", external_id="PMID:111"),
        make_evidence(intervention_name="Curcumin", external_id="PMID:222"),
    ]
    raw = make_llm_json(
        recommendations=[
            make_raw_recommendation(
                intervention_name="Curcumin",
                cited_study_ids=["PMID:111", "PMID:999-fake", "PMID:222"],
            )
        ]
    )
    result = parse_llm_response(raw, evidence)
    assert len(result.recommendations) == 1
    assert result.recommendations[0].cited_study_ids == ["PMID:111", "PMID:222"]


def test_recommendation_with_all_invalid_citations_is_dropped():
    evidence = [make_evidence(intervention_name="Curcumin", external_id="PMID:111")]
    raw = make_llm_json(
        recommendations=[
            make_raw_recommendation(intervention_name="Curcumin", cited_study_ids=["PMID:999-fake"])
        ]
    )
    result = parse_llm_response(raw, evidence)
    assert result.recommendations == []


def test_recommendation_with_empty_citations_list_is_dropped():
    evidence = [make_evidence(intervention_name="Curcumin", external_id="PMID:111")]
    raw = make_llm_json(
        recommendations=[make_raw_recommendation(intervention_name="Curcumin", cited_study_ids=[])]
    )
    result = parse_llm_response(raw, evidence)
    assert result.recommendations == []


def test_recommendation_missing_cited_study_ids_key_is_dropped():
    evidence = [make_evidence(intervention_name="Curcumin", external_id="PMID:111")]
    raw_rec = make_raw_recommendation(intervention_name="Curcumin")
    del raw_rec["cited_study_ids"]
    raw = make_llm_json(recommendations=[raw_rec])
    result = parse_llm_response(raw, evidence)
    assert result.recommendations == []


# ---------------------------------------------------------------------------
# parse_llm_response: multiple recommendations, mixed validity
# ---------------------------------------------------------------------------


def test_multiple_recommendations_some_valid_some_not():
    evidence = [
        make_evidence(intervention_name="Curcumin", external_id="PMID:111"),
        make_evidence(intervention_name="Berberine", external_id="PMID:222"),
    ]
    raw = make_llm_json(
        recommendations=[
            make_raw_recommendation(intervention_name="Curcumin", cited_study_ids=["PMID:111"]),
            make_raw_recommendation(intervention_name="Unknown Herb", cited_study_ids=["PMID:111"]),
            make_raw_recommendation(intervention_name="Berberine", cited_study_ids=["PMID:999-fake"]),
            make_raw_recommendation(intervention_name="Berberine", cited_study_ids=["PMID:222", "PMID:111"]),
        ]
    )
    result = parse_llm_response(raw, evidence)
    names = [r.intervention_name for r in result.recommendations]
    assert names == ["Curcumin", "Berberine"]
    berberine_rec = result.recommendations[1]
    assert berberine_rec.cited_study_ids == ["PMID:222", "PMID:111"]


def test_recommendation_with_invalid_enum_value_is_dropped():
    evidence = [make_evidence(intervention_name="Curcumin", external_id="PMID:111")]
    raw = make_llm_json(
        recommendations=[
            make_raw_recommendation(intervention_name="Curcumin", category="not-a-real-category")
        ]
    )
    result = parse_llm_response(raw, evidence)
    assert result.recommendations == []


def test_recommendation_with_invalid_evidence_level_is_dropped():
    evidence = [make_evidence(intervention_name="Curcumin", external_id="PMID:111")]
    raw = make_llm_json(
        recommendations=[
            make_raw_recommendation(intervention_name="Curcumin", evidence_level="super-duper-high")
        ]
    )
    result = parse_llm_response(raw, evidence)
    assert result.recommendations == []


def test_recommendation_null_typical_dose_and_rationale_allowed():
    evidence = [make_evidence(intervention_name="Curcumin", external_id="PMID:111")]
    raw_rec = make_raw_recommendation(intervention_name="Curcumin")
    raw_rec["typical_dose"] = None
    raw_rec["rationale"] = None
    raw = make_llm_json(recommendations=[raw_rec])
    result = parse_llm_response(raw, evidence)
    assert len(result.recommendations) == 1
    assert result.recommendations[0].typical_dose is None
    assert result.recommendations[0].rationale is None


def test_no_evidence_snippets_means_all_recommendations_dropped():
    raw = make_llm_json(recommendations=[make_raw_recommendation(intervention_name="Curcumin")])
    result = parse_llm_response(raw, [])
    assert result.recommendations == []
    # top-level analysis text is still preserved even with no evidence
    assert result.biomarker_pattern_analysis == "Elevated CRP suggests systemic inflammation."


def test_empty_recommendations_list_in_json():
    evidence = [make_evidence()]
    raw = make_llm_json(recommendations=[])
    result = parse_llm_response(raw, evidence)
    assert result.recommendations == []


# ---------------------------------------------------------------------------
# _valid_external_ids / _sanitize_recommendations (direct unit tests)
# ---------------------------------------------------------------------------


def test_valid_external_ids_returns_set_of_ids():
    evidence = [make_evidence(external_id="PMID:1"), make_evidence(external_id="PMID:2")]
    assert _valid_external_ids(evidence) == {"PMID:1", "PMID:2"}


def test_valid_external_ids_empty_list_returns_empty_set():
    assert _valid_external_ids([]) == set()


def test_sanitize_recommendations_filters_by_name_and_ids():
    raw = [
        make_raw_recommendation(intervention_name="Curcumin", cited_study_ids=["PMID:111"]),
        make_raw_recommendation(intervention_name="Ginkgo", cited_study_ids=["PMID:111"]),
    ]
    sanitized = _sanitize_recommendations(raw, valid_ids={"PMID:111"}, valid_intervention_names={"Curcumin"})
    assert len(sanitized) == 1
    assert sanitized[0].intervention_name == "Curcumin"


def test_sanitize_recommendations_skips_entries_failing_model_validation():
    raw = [
        {
            "intervention_name": "Curcumin",
            # missing required "mechanism" field
            "category": "herb",
            "evidence_level": "moderate",
            "cited_study_ids": ["PMID:111"],
        }
    ]
    sanitized = _sanitize_recommendations(raw, valid_ids={"PMID:111"}, valid_intervention_names={"Curcumin"})
    assert sanitized == []


# ---------------------------------------------------------------------------
# _build_payload
# ---------------------------------------------------------------------------


def test_build_payload_includes_all_expected_keys():
    labs = [make_lab()]
    pathways = [make_pathway()]
    evidence = [make_evidence()]
    payload = _build_payload(labs, pathways, evidence, {"age": 40})
    assert set(payload.keys()) == {"abnormal_biomarkers", "pathway_activations", "evidence", "health_profile"}


def test_build_payload_filters_out_normal_labs():
    labs = [make_lab(status=LabResultStatus.NORMAL), make_lab(status=LabResultStatus.HIGH)]
    payload = _build_payload(labs, [], [], {})
    assert len(payload["abnormal_biomarkers"]) == 1
    assert payload["abnormal_biomarkers"][0]["status"] == "high"


def test_build_payload_deidentifies_health_profile_strings():
    labs = [make_lab()]
    health_profile = {"notes": "Patient: John Smith has elevated CRP."}
    payload = _build_payload(labs, [], [], health_profile)
    assert "John Smith" not in payload["health_profile"]["notes"]
    assert "[REDACTED]" in payload["health_profile"]["notes"]


# ---------------------------------------------------------------------------
# generate_reasoning: empty evidence short-circuit
# ---------------------------------------------------------------------------


async def test_generate_reasoning_short_circuits_on_empty_evidence():
    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock()

    result = await generate_reasoning(
        normalized_labs=[make_lab()],
        pathway_activations=[make_pathway()],
        evidence_snippets=[],
        health_profile={},
        client=mock_client,
    )

    assert isinstance(result, LLMReasoningOutput)
    assert result.recommendations == []
    assert result.biomarker_pattern_analysis
    mock_client.messages.create.assert_not_called()


# ---------------------------------------------------------------------------
# generate_reasoning: happy path with mocked client
# ---------------------------------------------------------------------------


def _fake_response(json_text: str):
    resp = Mock()
    resp.content = [Mock(text=json_text)]
    return resp


async def test_generate_reasoning_calls_client_and_returns_parsed_output():
    evidence = [make_evidence(intervention_name="Curcumin", external_id="PMID:111")]
    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=_fake_response(make_llm_json()))

    result = await generate_reasoning(
        normalized_labs=[make_lab()],
        pathway_activations=[make_pathway()],
        evidence_snippets=evidence,
        health_profile={"age": 35},
        client=mock_client,
    )

    mock_client.messages.create.assert_awaited_once()
    assert isinstance(result, LLMReasoningOutput)
    assert len(result.recommendations) == 1
    assert result.recommendations[0].intervention_name == "Curcumin"


async def test_generate_reasoning_sends_expected_payload_keys():
    evidence = [make_evidence(intervention_name="Curcumin", external_id="PMID:111")]
    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=_fake_response(make_llm_json()))

    await generate_reasoning(
        normalized_labs=[make_lab()],
        pathway_activations=[make_pathway()],
        evidence_snippets=evidence,
        health_profile={"age": 35},
        client=mock_client,
    )

    _, kwargs = mock_client.messages.create.call_args
    sent_payload = json.loads(kwargs["messages"][0]["content"])
    assert set(sent_payload.keys()) == {
        "abnormal_biomarkers",
        "pathway_activations",
        "evidence",
        "health_profile",
    }
    assert sent_payload["health_profile"] == {"age": 35}
    assert len(sent_payload["abnormal_biomarkers"]) == 1
    assert sent_payload["evidence"][0]["intervention_name"] == "Curcumin"


async def test_generate_reasoning_deidentifies_outbound_payload():
    evidence = [make_evidence(intervention_name="Curcumin", external_id="PMID:111")]
    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=_fake_response(make_llm_json()))

    await generate_reasoning(
        normalized_labs=[make_lab()],
        pathway_activations=[make_pathway()],
        evidence_snippets=evidence,
        health_profile={"notes": "Patient: Jane Doe, DOB 01/02/1980"},
        client=mock_client,
    )

    _, kwargs = mock_client.messages.create.call_args
    sent_payload = json.loads(kwargs["messages"][0]["content"])
    assert "Jane Doe" not in sent_payload["health_profile"]["notes"]


async def test_generate_reasoning_uses_configured_model_and_system_prompt():
    evidence = [make_evidence(intervention_name="Curcumin", external_id="PMID:111")]
    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=_fake_response(make_llm_json()))

    await generate_reasoning(
        normalized_labs=[make_lab()],
        pathway_activations=[make_pathway()],
        evidence_snippets=evidence,
        health_profile={},
        client=mock_client,
    )

    _, kwargs = mock_client.messages.create.call_args
    assert kwargs["max_tokens"] == 4096
    assert "HerbaGraph" in kwargs["system"]
    assert "model" in kwargs


async def test_generate_reasoning_raises_llm_reasoning_error_on_malformed_json():
    evidence = [make_evidence(intervention_name="Curcumin", external_id="PMID:111")]
    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=_fake_response("this is not json"))

    with pytest.raises(LLMReasoningError):
        await generate_reasoning(
            normalized_labs=[make_lab()],
            pathway_activations=[make_pathway()],
            evidence_snippets=evidence,
            health_profile={},
            client=mock_client,
        )


async def test_generate_reasoning_sanitizes_bad_citations_from_llm():
    evidence = [make_evidence(intervention_name="Curcumin", external_id="PMID:111")]
    raw = make_llm_json(
        recommendations=[
            make_raw_recommendation(
                intervention_name="Curcumin", cited_study_ids=["PMID:111", "PMID:fake"]
            )
        ]
    )
    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=_fake_response(raw))

    result = await generate_reasoning(
        normalized_labs=[make_lab()],
        pathway_activations=[make_pathway()],
        evidence_snippets=evidence,
        health_profile={},
        client=mock_client,
    )

    assert result.recommendations[0].cited_study_ids == ["PMID:111"]


async def test_generate_reasoning_drops_recommendation_for_unlisted_intervention():
    evidence = [make_evidence(intervention_name="Curcumin", external_id="PMID:111")]
    raw = make_llm_json(
        recommendations=[
            make_raw_recommendation(intervention_name="Made Up Herb", cited_study_ids=["PMID:111"])
        ]
    )
    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=_fake_response(raw))

    result = await generate_reasoning(
        normalized_labs=[make_lab()],
        pathway_activations=[make_pathway()],
        evidence_snippets=evidence,
        health_profile={},
        client=mock_client,
    )

    assert result.recommendations == []


async def test_generate_reasoning_does_not_close_externally_provided_client():
    evidence = [make_evidence(intervention_name="Curcumin", external_id="PMID:111")]
    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=_fake_response(make_llm_json()))
    mock_client.close = AsyncMock()

    await generate_reasoning(
        normalized_labs=[make_lab()],
        pathway_activations=[make_pathway()],
        evidence_snippets=evidence,
        health_profile={},
        client=mock_client,
    )

    mock_client.close.assert_not_called()
