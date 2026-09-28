"""The saved case is read back in consumer words. The stored code stays put."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.models.discovery import DiscoveryCase, DiscoveryFinding
from app.models.enums import DiscoveryCaseStatus
from app.models.user import User

pytestmark = pytest.mark.asyncio


async def test_saved_check_reads_back_in_consumer_words(authed_client, db_session):
    saved = await authed_client.post(
        "/api/v1/cases/stack-check",
        json={
            "labs": [{"name": "LDL", "value": 162, "unit": "mg/dL"}],
            "stack": ["Red yeast rice"],
            "medications": ["Crestor"],
            "conditions": [],
        },
    )
    assert saved.status_code == 200, saved.text
    case_id = saved.json()["case_id"]
    before = (await db_session.execute(select(DiscoveryFinding))).scalars().all()

    report = await authed_client.get(f"/api/v1/cases/{case_id}/report")
    assert report.status_code == 200, report.text
    body = report.json()
    assert body["audience"] == "consumer"
    assert body["items"][0]["verdict"] == "hold"
    assert "statin" in body["items"][0]["text"].lower()
    assert "stop your statin" not in body["items"][0]["text"].lower()
    assert "monacolin" not in report.text.lower()
    assert "Crestor" not in report.text
    assert "mg" not in body["items"][0]["text"].lower()
    assert "caused" not in report.text.lower()
    assert body["labs"][0]["text"] == "LDL is outside the usual range."

    clinician = await authed_client.get(f"/api/v1/cases/{case_id}/report", params={"audience": "clinician"})
    assert clinician.status_code == 200, clinician.text
    assert clinician.json()["items"][0]["verdict"] == "hold"
    assert "Monacolin" in clinician.json()["items"][0]["text"]

    after = (await db_session.execute(select(DiscoveryFinding))).scalars().all()
    assert len(after) == len(before)
    case = await authed_client.get(f"/api/v1/cases/{case_id}")
    stored = [row for row in case.json()["findings"] if row["name"] == "Red yeast rice"]
    assert stored[0]["value"] == "hold"


async def test_empty_case_is_not_a_safe_report(authed_client, db_session, test_user):
    case = DiscoveryCase(
        user_id=test_user.id,
        presenting_concern="Burning feet",
        status=DiscoveryCaseStatus.OPEN,
    )
    db_session.add(case)
    await db_session.commit()
    report = await authed_client.get(f"/api/v1/cases/{case.id}/report")
    assert report.status_code == 200, report.text
    assert report.json()["items"] == []
    assert "not the same as safe" in report.json()["disclaimer"]
    assert "is safe" not in report.json()["disclaimer"]


async def test_another_account_cannot_read_the_report(authed_client, db_session, test_user):
    other = User(
        email=f"other-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="x",
        is_active=True,
        is_verified=True,
    )
    db_session.add(other)
    await db_session.flush()
    foreign = DiscoveryCase(
        user_id=other.id,
        presenting_concern="Not yours",
        status=DiscoveryCaseStatus.OPEN,
    )
    db_session.add(foreign)
    await db_session.commit()
    resp = await authed_client.get(f"/api/v1/cases/{foreign.id}/report")
    assert resp.status_code == 404, resp.text
    patient_id = test_user.id
    as_user = await authed_client.get(f"/api/v1/cases/{patient_id}/report")
    assert as_user.status_code == 404
