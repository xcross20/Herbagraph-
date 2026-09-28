"""Public Stack Check: bounded, unauthenticated, not stored, rate limited in the database."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import update

from app.api.public_rate_limit import MAX_HITS, enforce_public_rate_limit, increment_public_bucket
from app.models.public_rate_bucket import PublicRateBucket

_LDL = [{"name": "LDL", "value": 162, "unit": "mg/dL"}]


@pytest.mark.asyncio
async def test_crestor_and_red_yeast_rice_hold_without_auth(client):
    resp = await client.post(
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
async def test_blank_medication_list_does_not_clear_red_yeast_rice(client):
    resp = await client.post(
        "/api/v1/public/stack-check",
        json={"labs": _LDL, "stack": ["Red yeast rice"], "medications": None, "conditions": []},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["verdicts"][0]["verdict"] == "unknown"


@pytest.mark.asyncio
async def test_payload_is_bounded(client):
    too_many = await client.post(
        "/api/v1/public/stack-check",
        json={"labs": _LDL, "stack": [f"item {i}" for i in range(13)]},
    )
    assert too_many.status_code == 422
    long_name = await client.post(
        "/api/v1/public/stack-check",
        json={"labs": _LDL, "stack": ["x" * 81]},
    )
    assert long_name.status_code == 422


@pytest.mark.asyncio
async def test_twenty_first_check_is_rejected(client):
    body = {"labs": _LDL, "stack": ["Psyllium"], "medications": [], "conditions": []}
    for _ in range(MAX_HITS):
        ok = await client.post("/api/v1/public/stack-check", json=body)
        assert ok.status_code == 200, ok.text
    blocked = await client.post("/api/v1/public/stack-check", json=body)
    assert blocked.status_code == 429


@pytest.mark.asyncio
async def test_bucket_resets_when_the_window_expires(db_session):
    first = await increment_public_bucket(db_session, "public-stack:reset", 60)
    second = await increment_public_bucket(db_session, "public-stack:reset", 60)
    assert (first, second) == (1, 2)
    await db_session.execute(
        update(PublicRateBucket)
        .where(PublicRateBucket.bucket_key == "public-stack:reset")
        .values(window_started_epoch=0)
    )
    await db_session.commit()
    assert await increment_public_bucket(db_session, "public-stack:reset", 60) == 1


@pytest.mark.asyncio
async def test_database_outage_refuses_the_check(db_session):
    class _Request:
        headers: dict = {}
        client = None

    async def _broken(*_args, **_kwargs):
        raise ConnectionError("database down")

    db_session.execute = _broken  # type: ignore[method-assign]
    with pytest.raises(HTTPException) as caught:
        await enforce_public_rate_limit(_Request(), db_session)
    assert caught.value.status_code == 503
