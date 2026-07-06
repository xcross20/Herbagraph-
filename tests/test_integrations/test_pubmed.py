"""Unit tests for app.integrations.pubmed.search_pubmed (ESearch + ESummary)."""

import httpx
import pytest
import respx

from app.integrations.pubmed import search_pubmed
from app.models.enums import StudySource, StudyType

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]

_ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
_ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"


@pytest.fixture
async def client():
    async with httpx.AsyncClient() as c:
        yield c


@respx.mock
async def test_empty_esearch_idlist_returns_empty_list_without_calling_esummary(client):
    respx.get(_ESEARCH_URL).mock(
        return_value=httpx.Response(200, json={"esearchresult": {"idlist": []}})
    )
    esummary_route = respx.get(_ESUMMARY_URL).mock(
        return_value=httpx.Response(200, json={"result": {}})
    )

    results = await search_pubmed("curcumin", client, "Curcumin")

    assert results == []
    assert esummary_route.call_count == 0


@respx.mock
async def test_happy_path_builds_evidence_snippet(client):
    respx.get(_ESEARCH_URL).mock(
        return_value=httpx.Response(200, json={"esearchresult": {"idlist": ["12345"]}})
    )
    respx.get(_ESUMMARY_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "result": {
                    "12345": {
                        "title": "A Randomized Controlled Trial of Curcumin",
                        "pubtype": ["Journal Article", "Randomized Controlled Trial"],
                        "pubdate": "2021 Jun",
                    }
                }
            },
        )
    )

    results = await search_pubmed("curcumin", client, "Curcumin")

    assert len(results) == 1
    snippet = results[0]
    assert snippet.source == StudySource.PUBMED
    assert snippet.external_id == "PMID:12345"
    assert snippet.title == "A Randomized Controlled Trial of Curcumin"
    assert snippet.year == 2021
    assert snippet.study_type == StudyType.RCT
    assert snippet.quality_score == pytest.approx(0.85)
    assert snippet.url == "https://pubmed.ncbi.nlm.nih.gov/12345/"
    assert snippet.intervention_name == "Curcumin"
    assert snippet.abstract_snippet is None


@respx.mock
async def test_multiple_ids_build_multiple_snippets_in_order(client):
    respx.get(_ESEARCH_URL).mock(
        return_value=httpx.Response(200, json={"esearchresult": {"idlist": ["1", "2"]}})
    )
    respx.get(_ESUMMARY_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "result": {
                    "1": {"title": "First Study", "pubtype": [], "pubdate": "2019"},
                    "2": {"title": "Second Study meta-analysis", "pubtype": [], "pubdate": "2020"},
                }
            },
        )
    )

    results = await search_pubmed("query", client, "SomeHerb")

    assert [s.external_id for s in results] == ["PMID:1", "PMID:2"]
    assert results[0].study_type == StudyType.PRECLINICAL
    assert results[1].study_type == StudyType.META_ANALYSIS


@respx.mock
async def test_missing_summary_for_an_id_is_skipped_gracefully(client):
    respx.get(_ESEARCH_URL).mock(
        return_value=httpx.Response(200, json={"esearchresult": {"idlist": ["1", "2"]}})
    )
    respx.get(_ESUMMARY_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "result": {
                    "1": {"title": "Only This One Exists", "pubtype": [], "pubdate": "2020"},
                    # "2" missing entirely from the summary result
                }
            },
        )
    )

    results = await search_pubmed("query", client, "SomeHerb")

    assert len(results) == 1
    assert results[0].external_id == "PMID:1"


@respx.mock
async def test_year_parsing_extracts_four_digit_year_from_pubdate(client):
    respx.get(_ESEARCH_URL).mock(
        return_value=httpx.Response(200, json={"esearchresult": {"idlist": ["1"]}})
    )
    respx.get(_ESUMMARY_URL).mock(
        return_value=httpx.Response(
            200,
            json={"result": {"1": {"title": "T", "pubtype": [], "pubdate": "2018 Dec 15"}}},
        )
    )

    results = await search_pubmed("query", client, "SomeHerb")
    assert results[0].year == 2018


@respx.mock
async def test_year_parsing_returns_none_when_no_four_digit_token(client):
    respx.get(_ESEARCH_URL).mock(
        return_value=httpx.Response(200, json={"esearchresult": {"idlist": ["1"]}})
    )
    respx.get(_ESUMMARY_URL).mock(
        return_value=httpx.Response(
            200,
            json={"result": {"1": {"title": "T", "pubtype": [], "pubdate": ""}}},
        )
    )

    results = await search_pubmed("query", client, "SomeHerb")
    assert results[0].year is None


@respx.mock
async def test_missing_title_defaults_to_untitled(client):
    respx.get(_ESEARCH_URL).mock(
        return_value=httpx.Response(200, json={"esearchresult": {"idlist": ["1"]}})
    )
    respx.get(_ESUMMARY_URL).mock(
        return_value=httpx.Response(
            200,
            json={"result": {"1": {"pubtype": [], "pubdate": "2020"}}},
        )
    )

    results = await search_pubmed("query", client, "SomeHerb")
    assert results[0].title == "Untitled"
