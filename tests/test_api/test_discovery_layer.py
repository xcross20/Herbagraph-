"""Phases 1–6 + LLM: snapshot, documents, and PubMed on the existing Case API."""

import json
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.asyncio


async def test_emergency_facts_survive_rebuild_and_followup(authed_client):
    opened = await authed_client.post(
        "/api/v1/cases",
        json={
            "presenting_concern": (
                "Severe right upper pain for eight hours, can't stop vomiting and I'm running a fever."
            )
        },
    )
    assert opened.status_code == 201, opened.text
    first = opened.json()
    names = {item["name"] for item in first["findings"]}
    assert "abdominal_pain" in names or "fever" in names
    assert first["turn_state"]["safety_status"] == "S4"
    assert first["turn_state"]["discovery_can_continue"] is False
    follow = await authed_client.post(
        f"/api/v1/cases/{first['id']}/turns",
        json={"text": "What should I do?"},
    )
    assert follow.status_code == 200, follow.text
    body = follow.json()
    assert body["turn_state"]["safety_status"] == "S4"
    assert body["turn_state"]["discovery_can_continue"] is False
    later = {item["name"] for item in body["findings"]}
    assert "fever" in later
    assert any(name.startswith("patient_interpretation") or name == "abdominal_pain" for name in later)


async def test_user_can_remove_a_memory_item(authed_client):
    opened = await authed_client.post(
        "/api/v1/cases",
        json={"presenting_concern": "For six months, my feet have burned at night."},
    )
    case_id = opened.json()["id"]
    names = {item["name"] for item in opened.json()["findings"]}
    target = "burning sensation" if "burning sensation" in names else next(iter(names))
    removed = await authed_client.delete(f"/api/v1/cases/{case_id}/findings/{target}")
    assert removed.status_code == 200, removed.text
    later = {item["name"] for item in removed.json()["findings"]}
    assert target not in later


async def test_case_stream_accepts_then_finishes(authed_client):
    resp = await authed_client.post(
        "/api/v1/cases/stream",
        json={"presenting_concern": "For six months, my feet have burned at night."},
    )
    assert resp.status_code == 200, resp.text
    rows = [json.loads(line) for line in resp.text.splitlines() if line.strip()]
    events = [row["event"] for row in rows]
    assert "accepted" in events
    assert "done" in events
    done = next(row for row in rows if row["event"] == "done")
    assert done["case"]["id"]
    assert done["case"]["turns"]


async def test_lab_document_is_rejected_with_409(authed_client):
    created = await authed_client.post(
        "/api/v1/cases",
        json={"presenting_concern": "burning feet at night"},
    )
    case_id = created.json()["id"]
    resp = await authed_client.post(
        f"/api/v1/cases/{case_id}/documents",
        json={
            "filename": "quest-panel.txt",
            "text": "Quest Diagnostics\nVitamin B12 210 pg/mL Reference Range 200-900",
        },
    )
    assert resp.status_code == 409, resp.text
    assert "lab" in resp.json()["detail"].lower()


async def test_emg_document_attaches_report_finding(authed_client):
    created = await authed_client.post(
        "/api/v1/cases",
        json={"presenting_concern": "burning feet at night"},
    )
    case_id = created.json()["id"]
    resp = await authed_client.post(
        f"/api/v1/cases/{case_id}/documents",
        json={
            "filename": "emg-report.txt",
            "text": "Needle EMG and nerve conduction studies were normal.",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["accepted"] is True
    assert body["kind"] == "emg"
    names = {item["name"]: item["value"] for item in body["case"]["findings"]}
    assert names["emg testing"] == "reported_normal"
    assert names["emg_report"] == "attached"
    blob = " ".join(t["text"].lower() for t in body["case"]["turns"])
    assert "you have" not in blob


async def test_longitudinal_snapshot_is_versioned_from_case(authed_client):
    patient = await authed_client.post("/api/v1/patients", json={"display_name": "Snap Patient"})
    patient_id = patient.json()["id"]
    opened = await authed_client.post(
        "/api/v1/cases",
        json={"presenting_concern": "burning feet at night", "patient_id": patient_id},
    )
    assert opened.status_code == 201, opened.text
    got = await authed_client.get(f"/api/v1/patients/{patient_id}/longitudinal-snapshot")
    assert got.status_code == 200, got.text
    body = got.json()
    assert body["version"] >= 1
    assert body["is_current"] is True
    assert "burning" in " ".join(body["payload"]["current_concerns"]).lower()
    assert "you have" not in str(body["payload"]).lower()
    refreshed = await authed_client.post(f"/api/v1/patients/{patient_id}/longitudinal-snapshot")
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()["version"] > body["version"]


async def test_snapshot_requires_owned_patient(authed_client):
    missing = await authed_client.get(
        "/api/v1/patients/00000000-0000-0000-0000-000000000001/longitudinal-snapshot"
    )
    assert missing.status_code == 404


async def test_snapshot_requires_auth(client):
    resp = await client.get(
        "/api/v1/patients/00000000-0000-0000-0000-000000000001/longitudinal-snapshot"
    )
    assert resp.status_code == 401


async def test_why_turn_attaches_digit_only_pubmed(authed_client, monkeypatch):
    async def fake_search(query, client, intervention_name, max_results=5):
        return [
            SimpleNamespace(external_id="PMID:31415926", title="Retrieved burning-feet paper", year=2019),
            SimpleNamespace(external_id="PMID:not-real", title="Invented", year=2024),
        ]

    monkeypatch.setattr("app.integrations.pubmed.search_pubmed", fake_search)
    created = await authed_client.post(
        "/api/v1/cases",
        json={"presenting_concern": "For six months, my feet have burned at night."},
    )
    case_id = created.json()["id"]
    resp = await authed_client.post(
        f"/api/v1/cases/{case_id}/turns",
        json={"text": "Why? Show me the evidence."},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["turn_state"]["selected_action"]["type"] == "retrieve_evidence"
    assert body["literature"]
    assert {row["pmid"] for row in body["literature"]} == {"31415926"}
    assert body["literature"][0]["url"].endswith("/31415926/")
    assert all(row["pmid"].isdigit() for row in body["literature"])
    assert "you have" not in body["turns"][-1]["text"].lower()
