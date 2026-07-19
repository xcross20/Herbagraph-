#!/usr/bin/env python
"""Verify USDA_KEY is configured and FoodData Central responds.

Does not print the key. Safe for CI logs and Railway run output.

Usage:
  python scripts/verify_usda_key.py
  railway run python scripts/verify_usda_key.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402

from app.integrations.usda_fooddata import search_food, usda_api_key, usda_configured  # noqa: E402


async def main() -> int:
    configured = usda_configured()
    key = usda_api_key()
    print(f"usda_configured: {configured}")
    print(f"key_present: {bool(key)}")
    print(f"key_len: {len(key) if key else 0}")
    if not configured:
        print("FAIL: USDA_KEY is not set")
        return 1
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            foods = await search_food("blueberries", client, page_size=3)
        print(f"live_search_results: {len(foods)}")
        for food in foods[:3]:
            print(
                f"  fdcId={food.get('fdcId')} type={food.get('dataType')} "
                f"desc={str(food.get('description') or '')[:70]}"
            )
        if not foods:
            print("WARN: search returned 0 results (key may still be valid)")
            return 0
        print("OK: USDA FoodData Central reachable with configured key")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {type(exc).__name__}: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
