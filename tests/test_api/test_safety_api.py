"""Safety Engine API endpoints."""

import pytest

pytestmark = pytest.mark.asyncio


async def test_list_medications(authed_client):
    resp = await authed_client.get("/api/v1/safety/medications")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) >= 30
    names = {m["name"] for m in body}
    assert "Warfarin" in names
    assert "Metformin" in names


async def test_list_conditions(authed_client):
    resp = await authed_client.get("/api/v1/safety/conditions")
    assert resp.status_code == 200
    keys = {c["key"] for c in resp.json()}
    assert "pregnancy" in keys
    assert "liver_disease" in keys


async def test_evaluate_interventions(authed_client):
    resp = await authed_client.post(
        "/api/v1/safety/evaluate",
        json={
            "recommendations": [
                {
                    "intervention_name": "Curcumin",
                    "category": "herb",
                    "mechanism": "NF-kB modulation",
                    "evidence_level": "moderate",
                }
            ],
            "health_profile": {"current_medications": ["Warfarin"], "known_conditions": []},
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["intervention_name"] == "Curcumin"
    assert body[0]["safety_profile"]["safety_rating"] in ("moderate", "high", "low")