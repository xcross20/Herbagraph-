"""USDA FoodData Central API — canonical food entity normalization."""

from __future__ import annotations

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import get_settings

_BASE_URL = "https://api.nal.usda.gov/fdc/v1"

_retry_transient = retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, max=4),
    retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
)


def usda_api_key(explicit: str | None = None) -> str | None:
    """Resolve USDA FDC API key from argument or USDA_KEY env."""
    if explicit and explicit.strip():
        return explicit.strip()
    configured = (get_settings().usda_key or "").strip()
    return configured or None


def usda_configured() -> bool:
    return usda_api_key() is not None


@_retry_transient
async def search_food(
    query: str,
    client: httpx.AsyncClient,
    *,
    page_size: int = 5,
    api_key: str | None = None,
) -> list[dict]:
    """Search FoodData Central for canonical food matches."""
    resolved_key = usda_api_key(api_key)
    params: dict[str, str | int] = {"query": query, "pageSize": page_size}
    if resolved_key:
        params["api_key"] = resolved_key
    response = await client.get(f"{_BASE_URL}/foods/search", params=params)
    if response.status_code == 404:
        return []
    if response.status_code == 403 and not resolved_key:
        raise httpx.HTTPStatusError(
            "USDA FoodData Central requires an API key (set USDA_KEY)",
            request=response.request,
            response=response,
        )
    response.raise_for_status()
    foods = response.json().get("foods") or []
    results = [
        {
            "fdcId": item.get("fdcId"),
            "description": item.get("description"),
            "dataType": item.get("dataType"),
            "foodCategory": item.get("foodCategory"),
        }
        for item in foods
        if item.get("fdcId")
    ]
    return rank_usda_foods(results)


_USDA_DATA_TYPE_RANK = {
    "Foundation": 0,
    "SR Legacy": 1,
    "Survey (FNDDS)": 2,
    "Branded": 3,
}


def rank_usda_foods(foods: list[dict]) -> list[dict]:
    """Prefer Foundation / SR Legacy over branded supermarket SKUs."""
    return sorted(
        foods,
        key=lambda item: (
            _USDA_DATA_TYPE_RANK.get(str(item.get("dataType") or ""), 9),
            str(item.get("description") or ""),
        ),
    )