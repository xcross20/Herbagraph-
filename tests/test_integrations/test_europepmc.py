"""Unit tests for app.integrations.europepmc.search_europepmc."""

import httpx
import pytest
import respx

from app.integrations.europepmc import search_europepmc
from app.models.enums import StudySource, StudyType

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]

_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


@pytest.fixture
async def client():
    async with httpx.AsyncClient() as c:
        yield c


def _result(result_id="PMC123", title="A Study", pub_year="2021", pub_type="", doi=None, abstract=None):
    result = {"id": result_id, "title": title, "pubYear": pub_year, "pubType": pub_type}
    if doi is not None:
        result["doi"] = doi
    if abstract is not None:
        result["abstractText"] = abstract
    return result


@respx.mock
async def test_happy_path_parses_fields_with_doi(client):
    respx.get(_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "resultList": {
                    "result": [
                        _result(
                            result_id="PMC999",
                            title="Randomized Controlled Trial of Ashwagandha",
                            pub_year="2022",
                            doi="10.1234/abcd",
                            abstract="Some abstract text",
                        )
                    ]
                }
            },
        )
    )

    results = await search_europepmc("ashwagandha", client, "Ashwagandha")

    assert len(results) == 1
    snippet = results[0]
    assert snippet.source == StudySource.EUROPEPMC
    assert snippet.external_id == "EPMC:PMC999"
    assert snippet.title == "Randomized Controlled Trial of Ashwagandha"
    assert snippet.year == 2022
    assert snippet.study_type == StudyType.RCT
    assert snippet.quality_score == pytest.approx(0.85)
    assert snippet.url == "https://doi.org/10.1234/abcd"
    assert snippet.abstract_snippet == "Some abstract text"
    assert snippet.intervention_name == "Ashwagandha"


@respx.mock
async def test_url_falls_back_to_europepmc_when_no_doi(client):
    respx.get(_URL).mock(
        return_value=httpx.Response(
            200, json={"resultList": {"result": [_result(result_id="PMC555", doi=None)]}}
        )
    )

    results = await search_europepmc("query", client, "SomeHerb")
    assert results[0].url == "https://europepmc.org/article/MED/PMC555"


@respx.mock
async def test_missing_id_is_skipped(client):
    result_without_id = {"title": "No id here", "pubYear": "2020"}
    respx.get(_URL).mock(
        return_value=httpx.Response(
            200,
            json={"resultList": {"result": [result_without_id, _result(result_id="PMC1")]}},
        )
    )

    results = await search_europepmc("query", client, "SomeHerb")
    assert len(results) == 1
    assert results[0].external_id == "EPMC:PMC1"


@respx.mock
async def test_pub_year_non_numeric_yields_none(client):
    respx.get(_URL).mock(
        return_value=httpx.Response(
            200, json={"resultList": {"result": [_result(pub_year=None)]}}
        )
    )

    results = await search_europepmc("query", client, "SomeHerb")
    assert results[0].year is None


@respx.mock
async def test_missing_title_defaults_to_untitled(client):
    result = _result()
    del result["title"]
    respx.get(_URL).mock(return_value=httpx.Response(200, json={"resultList": {"result": [result]}}))

    results = await search_europepmc("query", client, "SomeHerb")
    assert results[0].title == "Untitled"


@respx.mock
async def test_pub_type_feeds_into_study_type_classification(client):
    respx.get(_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "resultList": {
                    "result": [_result(title="Curcumin effects", pub_type="meta-analysis")]
                }
            },
        )
    )

    results = await search_europepmc("query", client, "SomeHerb")
    assert results[0].study_type == StudyType.META_ANALYSIS


@respx.mock
async def test_no_results_returns_empty_list(client):
    respx.get(_URL).mock(return_value=httpx.Response(200, json={"resultList": {"result": []}}))
    results = await search_europepmc("query", client, "SomeHerb")
    assert results == []


@respx.mock
async def test_missing_result_list_returns_empty_list(client):
    respx.get(_URL).mock(return_value=httpx.Response(200, json={}))
    results = await search_europepmc("query", client, "SomeHerb")
    assert results == []
