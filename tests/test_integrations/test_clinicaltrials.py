"""Unit tests for app.integrations.clinicaltrials.search_clinicaltrials."""

import httpx
import pytest
import respx

from app.integrations.clinicaltrials import search_clinicaltrials
from app.models.enums import StudySource, StudyType

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]

_URL = "https://clinicaltrials.gov/api/v2/studies"


@pytest.fixture
async def client():
    async with httpx.AsyncClient() as c:
        yield c


def _study(nct_id="NCT00000001", brief_title="A Study", study_type="INTERVENTIONAL", start_date="2020-05-01"):
    return {
        "protocolSection": {
            "identificationModule": {"nctId": nct_id, "briefTitle": brief_title},
            "designModule": {"studyType": study_type},
            "statusModule": {"startDateStruct": {"date": start_date}},
        }
    }


@respx.mock
async def test_happy_path_parses_all_fields(client):
    respx.get(_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "studies": [
                    _study(
                        nct_id="NCT01234567",
                        brief_title="Curcumin for Inflammation",
                        study_type="INTERVENTIONAL",
                        start_date="2019-03-15",
                    )
                ]
            },
        )
    )

    results = await search_clinicaltrials("curcumin", client, "Curcumin")

    assert len(results) == 1
    snippet = results[0]
    assert snippet.source == StudySource.CLINICALTRIALS
    assert snippet.external_id == "NCT01234567"
    assert snippet.title == "Curcumin for Inflammation"
    assert snippet.year == 2019
    assert snippet.study_type == StudyType.RCT
    assert snippet.quality_score == pytest.approx(0.85)
    assert snippet.url == "https://clinicaltrials.gov/study/NCT01234567"
    assert snippet.intervention_name == "Curcumin"


@respx.mock
async def test_observational_study_type_maps_to_cohort(client):
    respx.get(_URL).mock(
        return_value=httpx.Response(200, json={"studies": [_study(study_type="OBSERVATIONAL")]})
    )

    results = await search_clinicaltrials("query", client, "SomeHerb")
    assert results[0].study_type == StudyType.COHORT
    assert results[0].quality_score == pytest.approx(0.60)


@pytest.mark.parametrize(
    "study_type_raw",
    ["INTERVENTIONAL", "EXPANDED_ACCESS", "", None],
)
@respx.mock
async def test_non_observational_study_types_map_to_rct(client, study_type_raw):
    study = _study()
    if study_type_raw is None:
        del study["protocolSection"]["designModule"]["studyType"]
    else:
        study["protocolSection"]["designModule"]["studyType"] = study_type_raw
    respx.get(_URL).mock(return_value=httpx.Response(200, json={"studies": [study]}))

    results = await search_clinicaltrials("query", client, "SomeHerb")
    assert results[0].study_type == StudyType.RCT


@respx.mock
async def test_observational_case_insensitive(client):
    study = _study(study_type="observational")
    respx.get(_URL).mock(return_value=httpx.Response(200, json={"studies": [study]}))

    results = await search_clinicaltrials("query", client, "SomeHerb")
    assert results[0].study_type == StudyType.COHORT


@respx.mock
async def test_missing_nct_id_is_skipped(client):
    study = _study()
    del study["protocolSection"]["identificationModule"]["nctId"]
    respx.get(_URL).mock(
        return_value=httpx.Response(200, json={"studies": [study, _study(nct_id="NCT99999999")]})
    )

    results = await search_clinicaltrials("query", client, "SomeHerb")
    assert len(results) == 1
    assert results[0].external_id == "NCT99999999"


@respx.mock
async def test_missing_brief_title_defaults_to_untitled(client):
    study = _study()
    del study["protocolSection"]["identificationModule"]["briefTitle"]
    respx.get(_URL).mock(return_value=httpx.Response(200, json={"studies": [study]}))

    results = await search_clinicaltrials("query", client, "SomeHerb")
    assert results[0].title == "Untitled"


@respx.mock
async def test_missing_start_date_yields_none_year(client):
    study = _study()
    study["protocolSection"]["statusModule"] = {}
    respx.get(_URL).mock(return_value=httpx.Response(200, json={"studies": [study]}))

    results = await search_clinicaltrials("query", client, "SomeHerb")
    assert results[0].year is None


@respx.mock
async def test_no_studies_returns_empty_list(client):
    respx.get(_URL).mock(return_value=httpx.Response(200, json={"studies": []}))

    results = await search_clinicaltrials("query", client, "SomeHerb")
    assert results == []


@respx.mock
async def test_multiple_studies_all_parsed(client):
    respx.get(_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "studies": [
                    _study(nct_id="NCT00000001", brief_title="First"),
                    _study(nct_id="NCT00000002", brief_title="Second", study_type="OBSERVATIONAL"),
                ]
            },
        )
    )

    results = await search_clinicaltrials("query", client, "SomeHerb")
    assert [s.external_id for s in results] == ["NCT00000001", "NCT00000002"]
    assert results[0].study_type == StudyType.RCT
    assert results[1].study_type == StudyType.COHORT
