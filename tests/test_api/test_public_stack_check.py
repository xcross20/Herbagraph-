"""Public Stack Check: bounded, unauthenticated, not stored, rate limited."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.api.public_rate_limit import MAX_HITS, MemoryRateStore, RedisRateStore, enforce_public_rate_limit
from app.main import app
from app.api.v1.public import get_public_rate_store

_LDL = [{"name": "LDL", "value": 162, "unit": "mg/dL"}]


class _FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, int] = {}
        self.ttls: dict[str, int] = {}
        self.expire_calls = 0

    def incr(self, key: str) -> int:
        self.values[key] = self.values.get(key, 0) + 1
        return self.values[key]

    def expire(self, key: str, seconds: int) -> bool:
        self.expire_calls += 1
        self.ttls[key] = seconds
        return True


class _DownRedis:
    def incr(self, key: str) -> int:
        raise ConnectionError("redis down")


@pytest.fixture
def limited(client):
    store = MemoryRateStore()
    app.dependency_overrides[get_public_rate_store] = lambda: store
    return client


@pytest.mark.asyncio
async def test_crestor_and_red_yeast_rice_hold_without_auth(limited):
    resp = await limited.post(
        "/api/v1/public/stack-check",
        json={"labs": _LDL, "stack": ["Red yeast rice"], "medications": ["Crestor"], "conditions": []},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["verdicts"][0]["verdict"] == "hold"
    assert "id" not in body
    assert "Crestor" not in resp.text
    assert "stored" in body["disclaimer"].lower()


@pytest.mark.asyncio
async def test_blank_medication_list_does_not_clear_red_yeast_rice(limited):
    resp = await limited.post(
        "/api/v1/public/stack-check",
        json={"labs": _LDL, "stack": ["Red yeast rice"], "medications": None, "conditions": []},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["verdicts"][0]["verdict"] == "unknown"


@pytest.mark.asyncio
async def test_payload_is_bounded(limited):
    too_many = await limited.post(
        "/api/v1/public/stack-check",
        json={"labs": _LDL, "stack": [f"item {i}" for i in range(13)]},
    )
    assert too_many.status_code == 422
    long_name = await limited.post(
        "/api/v1/public/stack-check",
        json={"labs": _LDL, "stack": ["x" * 81]},
    )
    assert long_name.status_code == 422


@pytest.mark.asyncio
async def test_twenty_first_check_is_rejected(limited):
    body = {"labs": _LDL, "stack": ["Psyllium"], "medications": [], "conditions": []}
    for _ in range(MAX_HITS):
        ok = await limited.post("/api/v1/public/stack-check", json=body)
        assert ok.status_code == 200, ok.text
    blocked = await limited.post("/api/v1/public/stack-check", json=body)
    assert blocked.status_code == 429


def test_redis_store_sets_ttl_once():
    client = _FakeRedis()
    store = RedisRateStore(client)
    assert store.increment("public-stack:1", 60) == 1
    assert store.increment("public-stack:1", 60) == 2
    assert client.expire_calls == 1
    assert client.ttls["public-stack:1"] == 60


def test_redis_outage_refuses_the_check():
    class _Request:
        headers: dict = {}
        client = None

    with pytest.raises(HTTPException) as caught:
        enforce_public_rate_limit(_Request(), RedisRateStore(_DownRedis()))
    assert caught.value.status_code == 503
