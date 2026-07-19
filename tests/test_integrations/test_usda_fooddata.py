"""Unit tests for USDA FoodData Central integration."""

import httpx
import pytest
import respx

from app.config import get_settings
from app.integrations.usda_fooddata import rank_usda_foods, search_food, usda_api_key, usda_configured

pytestmark = pytest.mark.unit

_SEARCH_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"


@pytest.fixture
async def client():
    async with httpx.AsyncClient() as c:
        yield c


def test_usda_api_key_reads_usda_key_env(monkeypatch):
    monkeypatch.setenv("USDA_KEY", "demo-usda-key")
    get_settings.cache_clear()
    assert usda_api_key() == "demo-usda-key"
    assert usda_configured() is True
    get_settings.cache_clear()


def test_usda_api_key_explicit_overrides_env(monkeypatch):
    monkeypatch.setenv("USDA_KEY", "from-env")
    get_settings.cache_clear()
    assert usda_api_key("from-arg") == "from-arg"
    get_settings.cache_clear()


@pytest.mark.asyncio
@respx.mock
async def test_search_food_includes_api_key_from_settings(client, monkeypatch):
    monkeypatch.setenv("USDA_KEY", "secret-usda-key")
    get_settings.cache_clear()

    route = respx.get(_SEARCH_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "foods": [
                    {
                        "fdcId": 2345678,
                        "description": "Blueberries, raw",
                        "dataType": "Foundation",
                        "foodCategory": "Fruits and Fruit Juices",
                    }
                ]
            },
        )
    )

    results = await search_food("blueberry", client, page_size=3)
    assert len(results) == 1
    assert results[0]["fdcId"] == 2345678
    assert route.called
    assert route.calls[0].request.url.params.get("api_key") == "secret-usda-key"
    assert route.calls[0].request.url.params.get("query") == "blueberry"
    get_settings.cache_clear()


@pytest.mark.asyncio
@respx.mock
async def test_search_food_404_returns_empty_list(client):
    respx.get(_SEARCH_URL).mock(return_value=httpx.Response(404))
    results = await search_food("nonexistent-food-xyz", client, api_key="test-key")
    assert results == []


def test_rank_usda_foods_prefers_foundation_over_branded():
    ranked = rank_usda_foods(
        [
            {"fdcId": 1, "description": "SPINACH", "dataType": "Branded"},
            {"fdcId": 2, "description": "Spinach, raw", "dataType": "Foundation"},
            {"fdcId": 3, "description": "Spinach", "dataType": "SR Legacy"},
        ]
    )
    assert ranked[0]["fdcId"] == 2
    assert ranked[1]["fdcId"] == 3
    assert ranked[2]["fdcId"] == 1