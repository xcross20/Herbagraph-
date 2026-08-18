"""PR-52: owner scope, audit, and PHI-safe telemetry."""

from __future__ import annotations

import pytest

from app.core.security import create_access_token
from app.discovery.telemetry import increment, reset, snapshot
from app.models.user import HealthProfile, User


@pytest.mark.asyncio
async def test_user_cannot_read_or_mutate_another_users_case(client, db_session):
    owner = User(email="owner-idor@example.com", hashed_password="x", is_active=True, is_verified=True)
    other = User(email="other-idor@example.com", hashed_password="x", is_active=True, is_verified=True)
    db_session.add_all([owner, other])
    await db_session.flush()
    db_session.add_all([HealthProfile(user_id=owner.id), HealthProfile(user_id=other.id)])
    await db_session.commit()

    owner_headers = {"Authorization": f"Bearer {create_access_token(str(owner.id))}"}
    other_headers = {"Authorization": f"Bearer {create_access_token(str(other.id))}"}

    created = await client.post(
        "/api/v1/cases",
        json={"presenting_concern": "For six months my feet have burned at night."},
        headers=owner_headers,
    )
    assert created.status_code == 201, created.text
    case_id = created.json()["id"]

    listed = await client.get("/api/v1/cases", headers=other_headers)
    assert listed.status_code == 200
    assert listed.json() == []

    for method, path, body in (
        ("GET", f"/api/v1/cases/{case_id}", None),
        ("GET", f"/api/v1/cases/{case_id}/investigation-map", None),
        ("GET", f"/api/v1/cases/{case_id}/turns", None),
        ("POST", f"/api/v1/cases/{case_id}/turns", {"text": "The burning is worse."}),
        (
            "POST",
            f"/api/v1/cases/{case_id}/documents",
            {"filename": "note.txt", "text": "clinical note"},
        ),
        (
            "POST",
            f"/api/v1/cases/{case_id}/monitoring",
            {
                "target": "burning sensation",
                "observation_time": "2026-08-18",
                "outcome_kind": "no_change",
                "source_event_id": "idor-1",
            },
        ),
        ("DELETE", f"/api/v1/cases/{case_id}/findings/onset", None),
        ("DELETE", f"/api/v1/cases/{case_id}", None),
    ):
        response = await client.request(method, path, json=body, headers=other_headers)
        assert response.status_code == 404, (path, response.status_code, response.text)

    visible = await client.get(f"/api/v1/cases/{case_id}", headers=owner_headers)
    assert visible.status_code == 200
    assert visible.json()["id"] == case_id


def test_telemetry_rejects_phi_like_counter_names():
    reset()
    increment("ssn:123-45-6789")
    increment("scientific_output_blocked")
    counts = snapshot()
    assert "ssn:123-45-6789" not in counts
    assert counts.get("phi_key_rejected") == 1
    assert counts.get("scientific_output_blocked") == 1
    reset()
