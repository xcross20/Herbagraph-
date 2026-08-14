"""API: Case is persisted and rebuild does not invent a diagnosis."""

import pytest

from app.models.enums import LabResultStatus

pytestmark = pytest.mark.asyncio


async def test_create_case_from_concern(authed_client):
    resp = await authed_client.post(
        "/api/v1/cases",
        json={"presenting_concern": "My feet burn at night for six months."},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["presenting_concern"].startswith("My feet burn")
    assert body["hypotheses"]
    assert all(h["diagnostic_certainty"] < h["investigation_relevance"] + 0.05 for h in body["hypotheses"])
    assert "diagnosis" in body["disclaimer"].lower()
    case_id = body["id"]

    got = await authed_client.get(f"/api/v1/cases/{case_id}")
    assert got.status_code == 200
    assert got.json()["id"] == case_id


async def test_rebuild_with_b12_labs_lists_mma_gap(authed_client):
    created = await authed_client.post(
        "/api/v1/cases",
        json={"presenting_concern": "burning feet at night"},
    )
    case_id = created.json()["id"]
    resp = await authed_client.post(
        f"/api/v1/cases/{case_id}/rebuild",
        json={
            "labs": [
                {"biomarker_name": "Vitamin B12", "value": 210, "status": LabResultStatus.LOW.value, "unit": "pg/mL"},
                {"biomarker_name": "MCV", "value": 104, "status": LabResultStatus.HIGH.value, "unit": "fL"},
            ]
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    b12 = next(h for h in body["hypotheses"] if h["code"] == "b12_functional_gap")
    assert "MMA" in b12["missing_markers"]
    assert b12["investigation_coverage"] < 1
    groups = {item["group"] for item in b12["investigations"]}
    assert {"core", "directed", "conditional"} <= groups
    listed = await authed_client.get("/api/v1/cases")
    assert listed.status_code == 200
    assert any(row["id"] == case_id for row in listed.json())


async def test_list_cases_can_filter_by_patient(authed_client, db_session, test_user):
    from app.models.patient import Patient

    patient = Patient(user_id=test_user.id, display_name="Clinic Patient")
    db_session.add(patient)
    await db_session.commit()
    await db_session.refresh(patient)

    first = await authed_client.post(
        "/api/v1/cases",
        json={"presenting_concern": "burning feet", "patient_id": str(patient.id)},
    )
    assert first.status_code == 201, first.text
    other = await authed_client.post(
        "/api/v1/cases",
        json={"presenting_concern": "fatigue without a patient"},
    )
    assert other.status_code == 201, other.text

    scoped = await authed_client.get(f"/api/v1/cases?patient_id={patient.id}")
    assert scoped.status_code == 200
    rows = scoped.json()
    assert len(rows) == 1
    assert rows[0]["patient_id"] == str(patient.id)
    assert "burning" in rows[0]["presenting_concern"]


async def test_case_requires_auth(client):
    resp = await client.post("/api/v1/cases", json={"presenting_concern": "fatigue"})
    assert resp.status_code == 401
