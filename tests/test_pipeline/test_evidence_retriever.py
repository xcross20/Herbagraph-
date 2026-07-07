"""Unit tests for Stage 4: evidence_retriever.

Covers build_query, the pathway->intervention mapping helpers, and
retrieve_evidence's concurrency/dedupe/ranking/resilience behavior. The
per-source HTTP calls (search_pubmed/search_clinicaltrials/search_europepmc)
are patched with AsyncMock so we exercise only the orchestration logic here.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.models.enums import PathwayDirection, StudySource, StudyType
from app.pipeline.evidence_retriever import (
    build_intervention_pathway_map,
    build_query,
    interventions_for_activations,
    retrieve_evidence,
)
from app.pipeline.intervention_catalog import build_pathway_intervention_map
from app.schemas.pipeline import EvidenceSnippet, PathwayActivation

pytestmark = pytest.mark.unit


def make_activation(pathway_code: str, pathway_name: str = "Test Pathway") -> PathwayActivation:
    return PathwayActivation(
        pathway_code=pathway_code,
        pathway_name=pathway_name,
        activation_score=0.8,
        direction=PathwayDirection.ACTIVATED,
        contributing_biomarkers=["CRP"],
    )


def make_snippet(
    intervention_name: str,
    external_id: str,
    quality_score: float,
    source: StudySource = StudySource.PUBMED,
) -> EvidenceSnippet:
    return EvidenceSnippet(
        source=source,
        external_id=external_id,
        title="Some Title",
        study_type=StudyType.RCT,
        quality_score=quality_score,
        intervention_name=intervention_name,
    )


# ---------------------------------------------------------------------------
# build_query
# ---------------------------------------------------------------------------


def test_build_query_includes_intervention_and_pathway_name():
    query = build_query("Curcumin", "NF-kB Inflammation")
    assert "Curcumin" in query
    assert "NF-kB Inflammation" in query


def test_build_query_format():
    query = build_query("Berberine", "AMPK")
    assert query == '("Berberine"[Title/Abstract]) AND ("AMPK" OR clinical) AND (trial OR randomized)'


# ---------------------------------------------------------------------------
# interventions_for_activations
# ---------------------------------------------------------------------------


def test_interventions_for_activations_includes_pathway_with_interventions():
    activations = [make_activation("NF_KB")]
    result = interventions_for_activations(activations)
    assert result["NF_KB"] == build_pathway_intervention_map()["NF_KB"]


def test_interventions_for_activations_excludes_pathway_with_empty_intervention_list():
    activations = [make_activation("NOT_A_REAL_PATHWAY")]
    result = interventions_for_activations(activations)
    assert result == {}


def test_interventions_for_activations_excludes_unknown_pathway_code():
    activations = [make_activation("NOT_A_REAL_PATHWAY")]
    result = interventions_for_activations(activations)
    assert result == {}


def test_interventions_for_activations_mixed_pathways():
    activations = [make_activation("NF_KB"), make_activation("THYROID_HPT"), make_activation("HPA_AXIS")]
    result = interventions_for_activations(activations)
    assert set(result.keys()) == {"NF_KB", "THYROID_HPT", "HPA_AXIS"}


def test_interventions_for_activations_empty_input_returns_empty_dict():
    assert interventions_for_activations([]) == {}


# ---------------------------------------------------------------------------
# build_intervention_pathway_map
# ---------------------------------------------------------------------------


def test_build_intervention_pathway_map_inverts_mapping():
    mapping = build_intervention_pathway_map()
    assert "NF_KB" in mapping["Curcumin"]
    assert "GASTRIC_COLONIZATION" in mapping["Mastic Gum"]


def test_build_intervention_pathway_map_includes_thyroid_medication_context():
    mapping = build_intervention_pathway_map()
    assert "THYROID_HPT" in mapping["Levothyroxine"]


def test_build_intervention_pathway_map_ashwagandha_covers_stress_and_thyroid():
    mapping = build_intervention_pathway_map()
    assert mapping["Ashwagandha"] == ["HPA_AXIS", "THYROID_HPT"]


# ---------------------------------------------------------------------------
# retrieve_evidence: empty inputs
# ---------------------------------------------------------------------------


async def test_retrieve_evidence_no_activations_returns_empty_list():
    result = await retrieve_evidence([])
    assert result == []


async def test_retrieve_evidence_activations_with_no_interventions_returns_empty_list():
    activations = [make_activation("NOT_A_REAL_PATHWAY")]
    result = await retrieve_evidence(activations)
    assert result == []


# ---------------------------------------------------------------------------
# retrieve_evidence: dedupe/ranking/concurrency, with mocked source functions
# ---------------------------------------------------------------------------


def _no_catalog_snippets(*_args, **_kwargs):
    return []


@patch("app.pipeline.evidence_retriever.build_catalog_evidence_snippets", side_effect=_no_catalog_snippets)
@patch("app.pipeline.evidence_retriever.search_europepmc", new_callable=AsyncMock)
@patch("app.pipeline.evidence_retriever.search_clinicaltrials", new_callable=AsyncMock)
@patch("app.pipeline.evidence_retriever.search_pubmed", new_callable=AsyncMock)
async def test_retrieve_evidence_calls_all_three_sources_and_merges(
    mock_pubmed, mock_ct, mock_epmc, _mock_catalog
):
    mock_pubmed.return_value = [make_snippet("Ashwagandha", "PMID:1", 0.85, StudySource.PUBMED)]
    mock_ct.return_value = [make_snippet("Ashwagandha", "NCT1", 0.60, StudySource.CLINICALTRIALS)]
    mock_epmc.return_value = [make_snippet("Ashwagandha", "EPMC:1", 0.45, StudySource.EUROPEPMC)]

    activations = [make_activation("HPA_AXIS", "HPA Axis")]
    result = await retrieve_evidence(activations)

    hpa_interventions = build_pathway_intervention_map()["HPA_AXIS"]
    assert mock_pubmed.await_count == len(hpa_interventions)
    assert mock_ct.await_count == len(hpa_interventions)
    assert mock_epmc.await_count == len(hpa_interventions)
    # Mocks return the same Ashwagandha snippets for every intervention queried.
    assert len(result) == 3
    scores = [s.quality_score for s in result]
    assert scores == sorted(scores, reverse=True)


@patch("app.pipeline.evidence_retriever.build_catalog_evidence_snippets", side_effect=_no_catalog_snippets)
@patch("app.pipeline.evidence_retriever.search_europepmc", new_callable=AsyncMock)
@patch("app.pipeline.evidence_retriever.search_clinicaltrials", new_callable=AsyncMock)
@patch("app.pipeline.evidence_retriever.search_pubmed", new_callable=AsyncMock)
async def test_retrieve_evidence_dedupes_keeping_higher_quality_snippet(
    mock_pubmed, mock_ct, mock_epmc, _mock_catalog
):
    # Same intervention_name + external_id across two "sources" -> dedupe key collision.
    mock_pubmed.return_value = [make_snippet("Ashwagandha", "SAME_ID", 0.85, StudySource.PUBMED)]
    mock_ct.return_value = [make_snippet("Ashwagandha", "SAME_ID", 0.20, StudySource.CLINICALTRIALS)]
    mock_epmc.return_value = []

    activations = [make_activation("HPA_AXIS", "HPA Axis")]
    result = await retrieve_evidence(activations)

    assert len(result) == 1
    assert result[0].quality_score == pytest.approx(0.85)
    assert result[0].source == StudySource.PUBMED


@patch("app.pipeline.evidence_retriever.build_catalog_evidence_snippets", side_effect=_no_catalog_snippets)
@patch("app.pipeline.evidence_retriever.search_europepmc", new_callable=AsyncMock)
@patch("app.pipeline.evidence_retriever.search_clinicaltrials", new_callable=AsyncMock)
@patch("app.pipeline.evidence_retriever.search_pubmed", new_callable=AsyncMock)
async def test_retrieve_evidence_dedupe_keeps_higher_quality_regardless_of_arrival_order(
    mock_pubmed, mock_ct, mock_epmc, _mock_catalog
):
    # Lower quality arrives from pubmed, higher quality from clinicaltrials -- the
    # dedupe must still keep the higher one even though it's not first.
    mock_pubmed.return_value = [make_snippet("Ashwagandha", "SAME_ID", 0.20, StudySource.PUBMED)]
    mock_ct.return_value = [make_snippet("Ashwagandha", "SAME_ID", 0.85, StudySource.CLINICALTRIALS)]
    mock_epmc.return_value = []

    activations = [make_activation("HPA_AXIS", "HPA Axis")]
    result = await retrieve_evidence(activations)

    assert len(result) == 1
    assert result[0].quality_score == pytest.approx(0.85)
    assert result[0].source == StudySource.CLINICALTRIALS


@patch("app.pipeline.evidence_retriever.build_catalog_evidence_snippets", side_effect=_no_catalog_snippets)
@patch("app.pipeline.evidence_retriever.search_europepmc", new_callable=AsyncMock)
@patch("app.pipeline.evidence_retriever.search_clinicaltrials", new_callable=AsyncMock)
@patch("app.pipeline.evidence_retriever.search_pubmed", new_callable=AsyncMock)
async def test_retrieve_evidence_different_intervention_names_are_not_deduped(
    mock_pubmed, mock_ct, mock_epmc, _mock_catalog
):
    # Same external_id but different intervention_name -> distinct dedupe keys, both kept.
    mock_pubmed.side_effect = lambda query, client, intervention_name, max_results: [
        make_snippet(intervention_name, "SAME_ID", 0.5, StudySource.PUBMED)
    ]
    mock_ct.return_value = []
    mock_epmc.return_value = []

    activations = [make_activation("NF_KB", "NF-kB")]
    result = await retrieve_evidence(activations)

    expected = set(build_pathway_intervention_map()["NF_KB"])
    intervention_names = {s.intervention_name for s in result}
    assert intervention_names == expected
    assert len(result) == len(expected)


@patch("app.pipeline.evidence_retriever.build_catalog_evidence_snippets", side_effect=_no_catalog_snippets)
@patch("app.pipeline.evidence_retriever.search_europepmc", new_callable=AsyncMock)
@patch("app.pipeline.evidence_retriever.search_clinicaltrials", new_callable=AsyncMock)
@patch("app.pipeline.evidence_retriever.search_pubmed", new_callable=AsyncMock)
async def test_retrieve_evidence_results_sorted_descending_by_quality_score(
    mock_pubmed, mock_ct, mock_epmc, _mock_catalog
):
    mock_pubmed.return_value = [
        make_snippet("Ashwagandha", "A", 0.20),
        make_snippet("Ashwagandha", "B", 0.90),
        make_snippet("Ashwagandha", "C", 0.55),
    ]
    mock_ct.return_value = []
    mock_epmc.return_value = []

    activations = [make_activation("HPA_AXIS", "HPA Axis")]
    result = await retrieve_evidence(activations)

    scores = [s.quality_score for s in result]
    assert scores == sorted(scores, reverse=True)
    assert scores == [0.90, 0.55, 0.20]


@patch("app.pipeline.evidence_retriever.build_catalog_evidence_snippets", side_effect=_no_catalog_snippets)
@patch("app.pipeline.evidence_retriever.search_europepmc", new_callable=AsyncMock)
@patch("app.pipeline.evidence_retriever.search_clinicaltrials", new_callable=AsyncMock)
@patch("app.pipeline.evidence_retriever.search_pubmed", new_callable=AsyncMock)
async def test_retrieve_evidence_source_exception_does_not_break_other_sources(
    mock_pubmed, mock_ct, mock_epmc, _mock_catalog
):
    mock_pubmed.side_effect = RuntimeError("PubMed is down")
    mock_ct.return_value = [make_snippet("Ashwagandha", "NCT1", 0.60, StudySource.CLINICALTRIALS)]
    mock_epmc.return_value = [make_snippet("Ashwagandha", "EPMC:1", 0.45, StudySource.EUROPEPMC)]

    activations = [make_activation("HPA_AXIS", "HPA Axis")]
    result = await retrieve_evidence(activations)

    assert len(result) == 2
    sources = {s.source for s in result}
    assert sources == {StudySource.CLINICALTRIALS, StudySource.EUROPEPMC}


@patch("app.pipeline.evidence_retriever.search_europepmc", new_callable=AsyncMock)
@patch("app.pipeline.evidence_retriever.search_clinicaltrials", new_callable=AsyncMock)
@patch("app.pipeline.evidence_retriever.search_pubmed", new_callable=AsyncMock)
async def test_retrieve_evidence_all_sources_raising_still_returns_catalog_snippets(
    mock_pubmed, mock_ct, mock_epmc
):
    mock_pubmed.side_effect = RuntimeError("down")
    mock_ct.side_effect = RuntimeError("down")
    mock_epmc.side_effect = RuntimeError("down")

    activations = [make_activation("HPA_AXIS", "HPA Axis")]
    result = await retrieve_evidence(activations)

    assert len(result) >= 1
    assert any(snippet.intervention_name == "Ashwagandha" for snippet in result)
    assert all(snippet.external_id.startswith("PMID:") for snippet in result)


@patch("app.pipeline.evidence_retriever.build_catalog_evidence_snippets", side_effect=_no_catalog_snippets)
@patch("app.pipeline.evidence_retriever.search_europepmc", new_callable=AsyncMock)
@patch("app.pipeline.evidence_retriever.search_clinicaltrials", new_callable=AsyncMock)
@patch("app.pipeline.evidence_retriever.search_pubmed", new_callable=AsyncMock)
async def test_retrieve_evidence_deduplicates_intervention_shared_across_pathways(
    mock_pubmed, mock_ct, mock_epmc, _mock_catalog
):
    # Curcumin is implicated by both NF_KB and IL6_JAK_STAT3 -- it must only be
    # fetched/searched once, not once per pathway.
    mock_pubmed.return_value = [make_snippet("Curcumin", "PMID:1", 0.85)]
    mock_ct.return_value = []
    mock_epmc.return_value = []

    activations = [make_activation("NF_KB", "NF-kB"), make_activation("IL6_JAK_STAT3", "IL6/JAK/STAT3")]
    await retrieve_evidence(activations)

    curcumin_calls = [call for call in mock_pubmed.await_args_list if call.args[2] == "Curcumin"]
    assert len(curcumin_calls) == 1


@patch("app.pipeline.evidence_retriever.build_catalog_evidence_snippets", side_effect=_no_catalog_snippets)
@patch("app.pipeline.evidence_retriever.search_europepmc", new_callable=AsyncMock)
@patch("app.pipeline.evidence_retriever.search_clinicaltrials", new_callable=AsyncMock)
@patch("app.pipeline.evidence_retriever.search_pubmed", new_callable=AsyncMock)
async def test_retrieve_evidence_passes_max_results_per_source_through(
    mock_pubmed, mock_ct, mock_epmc, _mock_catalog
):
    mock_pubmed.return_value = []
    mock_ct.return_value = []
    mock_epmc.return_value = []

    activations = [make_activation("HPA_AXIS", "HPA Axis")]
    await retrieve_evidence(activations, max_results_per_source=3)

    assert mock_pubmed.await_args.args[3] == 3
    assert mock_ct.await_args.args[3] == 3
    assert mock_epmc.await_args.args[3] == 3
