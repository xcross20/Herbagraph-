"""Gold cases at real Ask/API boundaries. Not helper-only interpret_workup traces."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def test_api_burning_feet_emg_return_visit_map_and_monitoring(authed_client):
    created = await authed_client.post(
        "/api/v1/cases",
        json={"presenting_concern": "For six months my feet have burned at night."},
    )
    assert created.status_code == 201, created.text
    case_id = created.json()["id"]
    attached = await authed_client.post(
        f"/api/v1/cases/{case_id}/documents",
        json={
            "filename": "emg-report.txt",
            "text": "Needle EMG and nerve conduction studies were normal.",
        },
    )
    assert attached.status_code == 200, attached.text
    names = {item["name"]: item["value"] for item in attached.json()["case"]["findings"]}
    assert names["emg testing"] == "reported_normal"

    fetched = await authed_client.get(f"/api/v1/cases/{case_id}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == case_id
    assert "you have" not in fetched.text.lower()

    mapped = await authed_client.get(f"/api/v1/cases/{case_id}/investigation-map")
    assert mapped.status_code == 200, mapped.text
    body = mapped.json()
    assert body["not_disease_probability"] is True
    for branch in body.get("branches") or []:
        assert "certainty" not in branch
        assert "diagnostic_certainty" not in branch

    follow = await authed_client.post(
        f"/api/v1/cases/{case_id}/turns",
        json={"text": "The burning is still there on this return visit."},
    )
    assert follow.status_code == 200, follow.text
    returned = follow.json()
    assert returned["id"] == case_id
    assert any(item["name"] == "emg testing" for item in returned["findings"])

    monitored = await authed_client.post(
        f"/api/v1/cases/{case_id}/monitoring",
        json={
            "target": "burning sensation",
            "observation_time": "2026-08-17",
            "outcome_kind": "no_change",
            "source_event_id": "return-visit-1",
            "exposure": "none",
            "adherence": "unknown",
        },
    )
    assert monitored.status_code == 200, monitored.text
    assert monitored.json()["causal_claim"] is False


async def test_api_biliary_concern_plus_emg_does_not_diagnose(authed_client):
    created = await authed_client.post(
        "/api/v1/cases",
        json={"presenting_concern": "I think this is my gallbladder. I also had an EMG."},
    )
    assert created.status_code == 201, created.text
    case_id = created.json()["id"]
    attached = await authed_client.post(
        f"/api/v1/cases/{case_id}/documents",
        json={
            "filename": "emg-report.txt",
            "text": "Needle EMG and nerve conduction studies were normal.",
        },
    )
    assert attached.status_code == 200, attached.text
    payload = attached.json()
    blob = str(payload).lower()
    assert "you have small-fiber" not in blob
    assert "this confirms" not in blob
    assert "diagnosis" in payload["case"]["disclaimer"].lower()
    mapped = await authed_client.get(f"/api/v1/cases/{case_id}/investigation-map")
    assert mapped.status_code == 200, mapped.text
    assert "does_not_address" in mapped.text or mapped.json().get("not_disease_probability") is True


async def test_api_duplicate_turn_does_not_invent_diagnosis(authed_client):
    created = await authed_client.post(
        "/api/v1/cases",
        json={"presenting_concern": "For six months my feet have burned at night."},
    )
    case_id = created.json()["id"]
    first = await authed_client.post(
        f"/api/v1/cases/{case_id}/turns",
        json={"text": "The burning is worse at night."},
    )
    second = await authed_client.post(
        f"/api/v1/cases/{case_id}/turns",
        json={"text": "The burning is worse at night."},
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert "you have small-fiber" not in second.text.lower()


async def test_api_safety_escalation_survives_followup(authed_client):
    created = await authed_client.post(
        "/api/v1/cases",
        json={"presenting_concern": "Chest pain and I cannot catch my breath."},
    )
    case_id = created.json()["id"]
    follow = await authed_client.post(
        f"/api/v1/cases/{case_id}/turns",
        json={"text": "It is still happening on this return visit."},
    )
    assert created.status_code == 201
    assert follow.status_code == 200
    blob = follow.text.lower()
    assert "emergency" in blob or "urgent" in blob or follow.json().get("safety")
