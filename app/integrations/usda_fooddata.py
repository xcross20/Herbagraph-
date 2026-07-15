"""USDA FoodData Central API — canonical food entity normalization."""

from __future__ import annotations

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

_BASE_URL = "https://api.nal.usda.gov/fdc/v1"


_retry_transient = retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, max=4),
    retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
)


@_retry_transient
async def search_food(
    query: str,
    client: httpx.AsyncClient,
    *,
    page_size: int = 5,
    api_key: str | None = None,
) -> list[dict]:
    """Search FoodData Central for canonical food matches."""
    params: dict[str, str | int] = {"query": query, "pageSize": page_size}
    if api_key:
        params["api_key"] = api_key
    response = await client.get(f"{_BASE_URL}/foods/search", params=params)
    if response.status_code == 404:
        return []
    response.raise_for_status()
    foods = response.json().get("foods") or []
    return [
        {
            "fdcId": item.get("fdcId"),
            "description": item.get("description"),
            "dataType": item.get("dataType"),
            "foodCategory": item.get("foodCategory"),
        }
        for item in foods
        if item.get("fdcId")
    ]