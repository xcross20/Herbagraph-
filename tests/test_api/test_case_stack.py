"""A signed-in stack check is stored on the Case. Saved labs win over the form."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models.discovery import DiscoveryCase, DiscoveryFinding
from app.models.enums import DiscoveryCaseStatus, LabProcessingStage, LabReportStatus, LabResultStatus
from app.models.lab import LabReport, LabResult
from app.models.patient import Patient
from app.models.user import User
from app.pipeline.stack_verdicts import evaluate_stack

pytestmark = pytest.mark.asyncio

_SAVED = [
    {"name": "LDL", "value": 90, "unit": "mg/dL"},
    {"name": "HbA1c", "value": 5.2, "unit": "%"},
]
_TRAP = [{"name": "LDL", "value": 170, "unit": "mg/dL"}]


async def _panel(db, user, rows, *, created_at=None, path="manual://", case=None):
    report = LabReport(
        user_id=user.id,
        patient_id=None,
        original_filename="labs",
        encrypted_file_path=path,
        file_size_bytes=4,
        status=LabReportStatus.COMPLETE,
        processing_stage=LabProcessingStage.COMPLETE,
        created_at=created_at or datetime.now(timezone.utc),
    )
    db.add(report)
    await db.flush()
    for row in rows:
        db.add(
            LabResult(
                lab_report_id=report.id,
                biomarker_name=row["name"],
                value=row["value"],
                unit=row["unit"],
                status=LabResultStatus.OPTIMAL,
            )
        )
    if case is not None:
        case.lab_report_id = report.id
    await db.commit()
    return report


async def _case(db, user, concern="Burning feet", status=DiscoveryCaseStatus.OPEN):
    case = DiscoveryCase(
        user_id=user.id,
        presenting_concern=concern,
        status=status,
    )
    db.add(case)
    await db.commit()
    return case


def _body(**extra):
    payload = {
        "labs": _TRAP,
        "stack": ["Berberine"],
        "medications": [],
        "conditions": [],
    }
    payload.update(extra)
    return payload


async def test_saved_labs_win_over_the_numbers_just_typed(authed_client, db_session, test_user):
    case = await _case(db_session, test_user)
    report = await _panel(db_session, test_user, _SAVED, case=case)
    posted = evaluate_stack(labs=_TRAP, stack=["Berberine"], medications=[], conditions=[])
    assert posted["verdicts"][0]["verdict"] == "discuss"

    resp = await authed_client.post("/api/v1/cases/stack-check", json=_body())
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["labs_source"] == "saved_report"
    assert body["verdicts"][0]["verdict"] == "mismatch"
    assert body["verdicts"][0]["verdict"] != posted["verdicts"][0]["verdict"]
    assert body["case_id"] == str(case.id)
    assert body["lab_report_id"] == str(report.id)
    assert "The labs already saved were used." in body["disclaimer"]
    assert "monacolin" not in resp.text.lower()

    stored = (
        await db_session.execute(select(LabResult).where(LabResult.lab_report_id == report.id))
    ).scalars().all()
    assert {row.biomarker_name: row.value for row in stored} == {"LDL": 90, "HbA1c": 5.2}
    reports = (await db_session.execute(select(LabReport))).scalars().all()
    assert len(reports) == 1

    case_read = await authed_client.get(f"/api/v1/cases/{case.id}")
    assert case_read.status_code == 200, case_read.text
    findings = case_read.json()["findings"]
    stack_rows = [row for row in findings if row["name"] == "Berberine"]
    assert len(stack_rows) == 1
    assert stack_rows[0]["value"] == "mismatch"
    assert stack_rows[0]["source"] == "stack_check"
    assert case_read.json()["lab_report_id"] == str(report.id)


async def test_repeat_check_does_not_duplicate_the_finding_or_the_report(authed_client, db_session, test_user):
    first = await authed_client.post(
        "/api/v1/cases/stack-check",
        json={
            "labs": [{"name": "LDL", "value": 162, "unit": "mg/dL"}],
            "stack": ["Red yeast rice"],
            "medications": ["Crestor"],
            "conditions": [],
        },
    )
    assert first.status_code == 200, first.text
    assert first.json()["labs_source"] == "entered_with_check"
    assert first.json()["verdicts"][0]["verdict"] == "hold"
    assert "Crestor" not in first.text
    assert "monacolin" not in first.json()["verdicts"][0]["reason"].lower()

    second = await authed_client.post(
        "/api/v1/cases/stack-check",
        json={
            "labs": [{"name": "LDL", "value": 90, "unit": "mg/dL"}],
            "stack": ["Red yeast rice"],
            "medications": ["Crestor"],
            "conditions": [],
            "audience": "clinician",
        },
    )
    assert second.status_code == 200, second.text
    assert second.json()["labs_source"] == "saved_report"
    assert second.json()["verdicts"][0]["verdict"] == "hold"
    assert "Monacolin" in second.json()["verdicts"][0]["reason"]
    assert second.json()["case_id"] == first.json()["case_id"]
    assert second.json()["lab_report_id"] == first.json()["lab_report_id"]

    listed = await authed_client.get("/api/v1/cases")
    assert len(listed.json()) == 1
    findings = [row for row in listed.json()[0]["findings"] if row["name"] == "Red yeast rice"]
    assert findings == [
        {"kind": "context", "name": "Red yeast rice", "value": "hold", "status": "hold", "source": "stack_check"}
    ]
    stored = (await db_session.execute(select(LabResult))).scalars().one()
    assert stored.value == 162
    assert len((await db_session.execute(select(LabReport))).scalars().all()) == 1


async def test_two_open_cases_are_not_guessed(authed_client, db_session, test_user):
    first = await _case(db_session, test_user, "First")
    second = await _case(db_session, test_user, "Second")
    resp = await authed_client.post("/api/v1/cases/stack-check", json=_body())
    assert resp.status_code == 409, resp.text
    assert "case_id" in resp.json()["detail"]
    await db_session.refresh(first)
    await db_session.refresh(second)
    assert first.lab_report_id is None
    assert second.lab_report_id is None
    assert (await db_session.execute(select(DiscoveryFinding))).scalars().all() == []

    chosen = await authed_client.post("/api/v1/cases/stack-check", json=_body(case_id=str(second.id)))
    assert chosen.status_code == 200, chosen.text
    assert chosen.json()["case_id"] == str(second.id)
    await db_session.refresh(first)
    assert first.lab_report_id is None


async def test_closed_case_and_foreign_case_and_patient_id_do_not_receive_the_stack(
    authed_client, db_session, test_user
):
    closed = await _case(db_session, test_user, status=DiscoveryCaseStatus.CLOSED)
    refused = await authed_client.post("/api/v1/cases/stack-check", json=_body(case_id=str(closed.id)))
    assert refused.status_code == 409, refused.text

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
    patient = Patient(user_id=test_user.id, display_name="Self")
    db_session.add_all([foreign, patient])
    await db_session.commit()

    stolen = await authed_client.post("/api/v1/cases/stack-check", json=_body(case_id=str(foreign.id)))
    assert stolen.status_code == 404, stolen.text
    as_patient = await authed_client.post("/api/v1/cases/stack-check", json=_body(case_id=str(patient.id)))
    assert as_patient.status_code == 404, as_patient.text
    assert (await db_session.execute(select(DiscoveryFinding))).scalars().all() == []


async def test_a_newer_report_does_not_replace_the_one_already_on_the_case(authed_client, db_session, test_user):
    case = await _case(db_session, test_user)
    older = await _panel(
        db_session,
        test_user,
        _SAVED,
        created_at=datetime.now(timezone.utc) - timedelta(days=2),
        path="uploads/panel.pdf",
        case=case,
    )
    newer = await _panel(
        db_session,
        test_user,
        [{"name": "LDL", "value": 170, "unit": "mg/dL"}],
        created_at=datetime.now(timezone.utc),
    )
    resp = await authed_client.post("/api/v1/cases/stack-check", json=_body())
    assert resp.status_code == 200, resp.text
    assert resp.json()["lab_report_id"] == str(older.id)
    assert resp.json()["lab_report_id"] != str(newer.id)
    assert resp.json()["verdicts"][0]["verdict"] == "mismatch"
    kept = (
        await db_session.execute(select(LabResult).where(LabResult.lab_report_id == older.id))
    ).scalars().all()
    assert {row.biomarker_name: row.value for row in kept}["LDL"] == 90


async def test_public_stack_check_still_stores_nothing(client, db_session):
    resp = await client.post(
        "/api/v1/public/stack-check",
        json={
            "labs": [{"name": "LDL", "value": 162, "unit": "mg/dL"}],
            "stack": ["Red yeast rice"],
            "medications": ["Crestor"],
            "conditions": [],
        },
    )
    assert resp.status_code == 200, resp.text
    assert (await db_session.execute(select(DiscoveryCase))).scalars().all() == []
    assert (await db_session.execute(select(LabReport))).scalars().all() == []
    assert (await db_session.execute(select(DiscoveryFinding))).scalars().all() == []


async def test_signed_out_stack_check_is_refused(client):
    resp = await client.post("/api/v1/cases/stack-check", json=_body())
    assert resp.status_code == 401
