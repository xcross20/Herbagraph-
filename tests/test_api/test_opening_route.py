"""The opening route decides the door and does not create a case."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def test_burning_feet_with_supplements_stays_an_investigation(authed_client):
    resp = await authed_client.post(
        "/api/v1/cases/route",
        json={"text": "I've had burning feet for six months and I take magnesium and B12"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["door"] == "investigation"
    assert body["opens_case"] is True
    assert body["destination"] == "ask"
    listed = await authed_client.get("/api/v1/cases")
    assert listed.status_code == 200
    assert listed.json() == []


async def test_supplement_purchase_does_not_open_a_case(authed_client):
    resp = await authed_client.post(
        "/api/v1/cases/route",
        json={"text": "I'm considering berberine and red yeast rice. I'm on Crestor."},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["door"] == "stack_eval"
    assert resp.json()["opens_case"] is False
    assert resp.json()["destination"] == "stack"


async def test_labs_on_hand_go_to_the_lab_door(authed_client):
    resp = await authed_client.post(
        "/api/v1/cases/route",
        json={"text": "I already have labs. Take me to upload."},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"door": "labs_on_hand", "opens_case": False, "destination": "labs"}


async def test_safety_question_goes_to_stack_not_a_case(authed_client):
    resp = await authed_client.post(
        "/api/v1/cases/route",
        json={"text": "Is red yeast rice safe with my statin?"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["door"] == "safety"
    assert resp.json()["opens_case"] is False
    assert resp.json()["destination"] == "stack"
