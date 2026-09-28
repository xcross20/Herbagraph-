"""Follow-up compare reads two lab reports and does not rewrite the stack check."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select

from app.models.discovery import DiscoveryCase
from app.models.enums import DiscoveryCaseStatus, LabProcessingStage, LabReportStatus, LabResultStatus
from app.models.lab import LabReport, LabResult
from app.models.response_tracking import ResponseTracking
from app.models.user import User

pytestmark = pytest.mark.asyncio


async def test_later_labs_do_not_become_a_cause_or_a_new_stack_verdict(authed_client, db_session):
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
    baseline_id = saved.json()["lab_report_id"]

    compared = await authed_client.post(
        f"/api/v1/cases/{case_id}/follow-up",
        json={"labs": [{"name": "LDL", "value": 140, "unit": "mg/dL"}, {"name": "HbA1c", "value": 5.4, "unit": "%"}]},
    )
    assert compared.status_code == 200, compared.text
    body = compared.json()
    assert body["changes"][0]["name"] == "LDL"
    assert body["changes"][0]["direction"] == "improved"
    assert "not proof that a supplement produced the change" in body["changes"][0]["text"]
    assert body["missing"][0]["name"] == "HbA1c"
    assert body["missing"][0]["side"] == "baseline"
    assert body["baseline_lab_report_id"] == baseline_id
    assert body["follow_up_lab_report_id"] != baseline_id
    lowered = compared.text.lower()
    assert "caused" not in lowered
    assert "crestor" not in lowered
    assert "red yeast" not in lowered
    assert "intervention" not in lowered

    case = await authed_client.get(f"/api/v1/cases/{case_id}")
    assert case.json()["lab_report_id"] == baseline_id
    stored = [row for row in case.json()["findings"] if row["name"] == "Red yeast rice"]
    assert stored[0]["value"] == "hold"
    tracking = (await db_session.execute(select(func.count()).select_from(ResponseTracking))).scalar_one()
    assert tracking == 0

    same = await authed_client.post(
        f"/api/v1/cases/{case_id}/follow-up",
        json={"follow_up_lab_report_id": baseline_id},
    )
    assert same.status_code == 409, same.text


async def test_a_foreign_report_and_a_case_without_labs_do_not_compare(authed_client, db_session, test_user):
    owned = await authed_client.post(
        "/api/v1/cases/stack-check",
        json={
            "labs": [{"name": "LDL", "value": 162, "unit": "mg/dL"}],
            "stack": ["Berberine"],
            "medications": [],
            "conditions": [],
        },
    )
    assert owned.status_code == 200, owned.text
    other = User(
        email=f"other-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="x",
        is_active=True,
        is_verified=True,
    )
    empty = DiscoveryCase(
        user_id=test_user.id,
        presenting_concern="No labs",
        status=DiscoveryCaseStatus.OPEN,
    )
    db_session.add_all([empty, other])
    await db_session.flush()
    foreign = LabReport(
        user_id=other.id,
        original_filename="theirs",
        encrypted_file_path="uploads/theirs.pdf",
        file_size_bytes=4,
        status=LabReportStatus.COMPLETE,
        processing_stage=LabProcessingStage.COMPLETE,
    )
    db_session.add(foreign)
    await db_session.flush()
    db_session.add(
        LabResult(
            lab_report_id=foreign.id,
            biomarker_name="LDL",
            value=140,
            unit="mg/dL",
            status=LabResultStatus.HIGH,
        )
    )
    await db_session.commit()

    missing = await authed_client.post(
        f"/api/v1/cases/{empty.id}/follow-up",
        json={"labs": [{"name": "LDL", "value": 140, "unit": "mg/dL"}]},
    )
    assert missing.status_code == 409, missing.text

    stolen = await authed_client.post(
        f"/api/v1/cases/{owned.json()['case_id']}/follow-up",
        json={"follow_up_lab_report_id": str(foreign.id)},
    )
    assert stolen.status_code == 404, stolen.text
