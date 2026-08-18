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
    names = [item["name"] for item in second.json()["findings"]]
    assert names.count("burning sensation") <= 1


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


async def test_api_unreadable_lab_is_not_a_successful_discovery_parse(authed_client):
    created = await authed_client.post(
        "/api/v1/cases",
        json={"presenting_concern": "For six months my feet have burned at night."},
    )
    case_id = created.json()["id"]
    resp = await authed_client.post(
        f"/api/v1/cases/{case_id}/documents",
        json={"filename": "labs.pdf", "text": "%PDF-1.4 unreadable binary junk"},
    )
    assert resp.status_code == 409, resp.text
    assert "not a successful" in resp.text.lower() or "could not be parsed" in resp.text.lower()


async def test_api_ambiguous_mri_does_not_resolve_to_brain(authed_client):
    from app.discovery.resolver import resolve_test
    from app.models.enums import ResolverStatus

    created = await authed_client.post(
        "/api/v1/cases",
        json={"presenting_concern": "I had an MRI. My feet still burn."},
    )
    assert created.status_code == 201
    resolved = resolve_test("MRI")
    assert resolved.status is ResolverStatus.AMBIGUOUS
    assert resolved.match is None


async def test_api_contraindication_is_visible_on_safety_evaluate(authed_client):
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
    assert resp.status_code == 200, resp.text
    blob = resp.text.lower()
    assert "warfarin" in blob or "caution" in blob or "interact" in blob or "flag" in blob


async def test_api_correction_chain_visible_after_restart(authed_client, db_session):
    import uuid

    from app.discovery.engine import CaseSnapshot, FindingDraft
    from app.discovery.service import apply_snapshot
    from app.models.discovery import DiscoveryCase
    from sqlalchemy import select

    created = await authed_client.post(
        "/api/v1/cases",
        json={"presenting_concern": "For six months my feet have burned at night."},
    )
    case_id = uuid.UUID(created.json()["id"])
    case = (
        await db_session.execute(select(DiscoveryCase).where(DiscoveryCase.id == case_id))
    ).scalar_one()

    def snap(value: str) -> CaseSnapshot:
        return CaseSnapshot(
            presenting_concern=case.presenting_concern,
            findings=[
                FindingDraft(kind="context", name="onset", value=value, status=None, branch=None, source="user")
            ],
            hypotheses=[],
            branch_coverage=[],
            investigation_coverage=0.0,
        )

    await apply_snapshot(db_session, case, snap("after surgery"), source_event_id="http-a")
    await apply_snapshot(db_session, case, snap("before surgery"), source_event_id="http-b")
    await apply_snapshot(db_session, case, snap("after surgery"), source_event_id="http-a2")
    await db_session.commit()
    fetched = await authed_client.get(f"/api/v1/cases/{case_id}")
    assert fetched.status_code == 200
    onsets = [item["value"] for item in fetched.json()["findings"] if item["name"] == "onset"]
    assert onsets == ["after surgery"]


async def test_api_idempotent_turn_key_does_not_duplicate(authed_client):
    created = await authed_client.post(
        "/api/v1/cases",
        json={"presenting_concern": "For six months my feet have burned at night."},
    )
    case_id = created.json()["id"]
    first = await authed_client.post(
        f"/api/v1/cases/{case_id}/turns",
        json={"text": "The burning is worse at night.", "idempotency_key": "same-client-event"},
    )
    second = await authed_client.post(
        f"/api/v1/cases/{case_id}/turns",
        json={"text": "The burning is worse at night.", "idempotency_key": "same-client-event"},
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert len(first.json()["turns"]) == len(second.json()["turns"])


async def test_api_replay_correction_restart_and_inactivation(authed_client, db_session):
    import uuid

    from sqlalchemy import select

    from app.models.discovery import DiscoveryFinding

    created = await authed_client.post(
        "/api/v1/cases",
        json={"presenting_concern": "For six months my feet have burned at night."},
    )
    assert created.status_code == 201, created.text
    case_id = created.json()["id"]

    first = await authed_client.post(
        f"/api/v1/cases/{case_id}/turns",
        json={"text": "Onset was after surgery."},
    )
    replay = await authed_client.post(
        f"/api/v1/cases/{case_id}/turns",
        json={"text": "Onset was after surgery."},
    )
    assert first.status_code == 200
    assert replay.status_code == 200
    first_ids = {item["name"] for item in first.json()["findings"]}
    replay_ids = {item["name"] for item in replay.json()["findings"]}
    assert first_ids == replay_ids

    corrected = await authed_client.post(
        f"/api/v1/cases/{case_id}/turns",
        json={"text": "Correction: onset was before surgery."},
    )
    assert corrected.status_code == 200
    await db_session.commit()
    db_session.expire_all()
    restarted = await authed_client.get(f"/api/v1/cases/{case_id}")
    assert restarted.status_code == 200
    active_onsets = [
        item["value"]
        for item in restarted.json()["findings"]
        if item["name"] == "onset"
    ]
    if active_onsets:
        assert active_onsets == ["before surgery"] or "before surgery" in " ".join(
            str(item) for item in restarted.json()["findings"]
        )

    attached = await authed_client.post(
        f"/api/v1/cases/{case_id}/documents",
        json={"filename": "emg-report.txt", "text": "Needle EMG and nerve conduction studies were normal."},
    )
    assert attached.status_code == 200, attached.text
    assert any(item["name"] == "emg testing" for item in attached.json()["case"]["findings"])

    removed = await authed_client.delete(f"/api/v1/cases/{case_id}/findings/emg testing")
    assert removed.status_code == 200, removed.text
    assert all(item["name"] != "emg testing" for item in removed.json()["findings"])
    held = list(
        (
            await db_session.execute(
                select(DiscoveryFinding).where(DiscoveryFinding.case_id == uuid.UUID(case_id))
            )
        ).scalars()
    )
    emg_rows = [row for row in held if row.name == "emg testing"]
    assert emg_rows
    assert all(row.active is False for row in emg_rows)
