"""Unit tests for app.integrations.pubchem: get_compound_cid and get_compound_properties."""

import httpx
import pytest
import respx

from app.integrations.pubchem import get_compound_cid, get_compound_properties

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]

_CID_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/curcumin/cids/JSON"
_PROPS_URL = (
    "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/969516/property/"
    "MolecularFormula,MolecularWeight,IUPACName/JSON"
)


@pytest.fixture
async def client():
    async with httpx.AsyncClient() as c:
        yield c


@respx.mock
async def test_get_compound_cid_happy_path(client):
    respx.get(_CID_URL).mock(
        return_value=httpx.Response(200, json={"IdentifierList": {"CID": [969516]}})
    )

    cid = await get_compound_cid("curcumin", client)
    assert cid == 969516


@respx.mock
async def test_get_compound_cid_returns_first_of_multiple(client):
    respx.get(_CID_URL).mock(
        return_value=httpx.Response(200, json={"IdentifierList": {"CID": [111, 222]}})
    )

    cid = await get_compound_cid("curcumin", client)
    assert cid == 111


@respx.mock
async def test_get_compound_cid_404_returns_none(client):
    respx.get(_CID_URL).mock(return_value=httpx.Response(404))

    cid = await get_compound_cid("curcumin", client)
    assert cid is None


@respx.mock
async def test_get_compound_cid_empty_list_returns_none(client):
    respx.get(_CID_URL).mock(
        return_value=httpx.Response(200, json={"IdentifierList": {"CID": []}})
    )

    cid = await get_compound_cid("curcumin", client)
    assert cid is None


@respx.mock
async def test_get_compound_properties_happy_path(client):
    respx.get(_PROPS_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "PropertyTable": {
                    "Properties": [
                        {
                            "CID": 969516,
                            "MolecularFormula": "C21H20O6",
                            "MolecularWeight": "368.38",
                            "IUPACName": "curcumin",
                        }
                    ]
                }
            },
        )
    )

    properties = await get_compound_properties(969516, client)
    assert properties == {
        "CID": 969516,
        "MolecularFormula": "C21H20O6",
        "MolecularWeight": "368.38",
        "IUPACName": "curcumin",
    }


@respx.mock
async def test_get_compound_properties_404_returns_none(client):
    respx.get(_PROPS_URL).mock(return_value=httpx.Response(404))

    properties = await get_compound_properties(969516, client)
    assert properties is None


@respx.mock
async def test_get_compound_properties_empty_list_returns_none(client):
    respx.get(_PROPS_URL).mock(
        return_value=httpx.Response(200, json={"PropertyTable": {"Properties": []}})
    )

    properties = await get_compound_properties(969516, client)
    assert properties is None
