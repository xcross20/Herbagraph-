"""API: Case is persisted and rebuild does not invent a diagnosis."""

import json

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


async def test_clinician_case_uses_patient_context_not_owner_profile(
    authed_client, db_session, test_user
):
    from app.models.enums import PatientContextType, UserRole
    from app.models.patient import Patient
    from app.models.patient_context import PatientContext
    from app.models.user import HealthProfile
    from sqlalchemy import select

    test_user.role = UserRole.CLINICIAN
    profile = (
        await db_session.execute(select(HealthProfile).where(HealthProfile.user_id == test_user.id))
    ).scalar_one()
    profile.known_conditions = ["Owner-only diagnosis"]
    profile.current_medications = ["Owner-only drug"]
    patient = Patient(user_id=test_user.id, display_name="Clinic Patient", biological_sex="female")
    db_session.add(patient)
    await db_session.flush()
    db_session.add(
        PatientContext(
            patient_id=patient.id,
            context_type=PatientContextType.MEDICATION,
            name="Metformin",
            value="500mg",
            active=True,
        )
    )
    await db_session.commit()

    created = await authed_client.post(
        "/api/v1/cases",
        json={"presenting_concern": "burning feet", "patient_id": str(patient.id)},
    )
    assert created.status_code == 201, created.text
    findings = " ".join(f.get("value") or "" for f in created.json()["findings"])
    assert "Metformin" in findings
    assert "Owner-only" not in findings
    assert created.json()["monitor_plan"] is not None


async def test_answer_yes_records_outcome_and_closes_gap(authed_client):
    created = await authed_client.post(
        "/api/v1/cases",
        json={"presenting_concern": "burning feet at night"},
    )
    case_id = created.json()["id"]
    rebuilt = await authed_client.post(
        f"/api/v1/cases/{case_id}/rebuild",
        json={
            "labs": [
                {"biomarker_name": "Vitamin B12", "value": 210, "status": LabResultStatus.LOW.value, "unit": "pg/mL"},
                {"biomarker_name": "MCV", "value": 104, "status": LabResultStatus.HIGH.value, "unit": "fL"},
            ]
        },
    )
    assert rebuilt.status_code == 200, rebuilt.text
    question = next(q for q in rebuilt.json()["next_questions"] if "MMA" in q["closes"] or "mma" in q["closes"].lower())
    before = next(h for h in rebuilt.json()["hypotheses"] if h["code"] == "b12_functional_gap")
    assert "MMA" in before["missing_markers"]

    answered = await authed_client.post(
        f"/api/v1/cases/{case_id}/answers",
        json={"code": question["code"], "answer": "yes"},
    )
    assert answered.status_code == 200, answered.text
    body = answered.json()
    after = next(h for h in body["hypotheses"] if h["code"] == "b12_functional_gap")
    assert "MMA" not in after["missing_markers"]
    assert after["investigation_coverage"] > before["investigation_coverage"]
    assert any(o["label"] == "MMA" and o["status"] == "completed" for o in body["outcomes"])
    assert any(f["kind"] == "assessment" and f["name"] == "MMA" for f in body["findings"])
    assert any("diagnosis" not in (t["text"] or "").lower() or "not a diagnosis" in (t["text"] or "").lower() for t in body["turns"])
    assert all("you have" not in t["text"].lower() for t in body["turns"])


async def test_conversation_is_one_question_per_turn(authed_client):
    created = await authed_client.post(
        "/api/v1/cases",
        json={
            "presenting_concern": (
                "For six months, my feet have burned at night. My doctor says my blood work is normal."
            )
        },
    )
    assert created.status_code == 201, created.text
    opened = created.json()
    assert opened["current_question"] is not None
    assert opened["current_question"]["code"] == "q_laterality"
    assert opened["turn_state"]["selected_action"]["type"] == "ask_question"
    assert "you have" not in opened["turns"][-1]["text"].lower()
    assert "small-fiber neuropathy" not in opened["turns"][-1]["text"].lower()
    names = {item["name"] for item in opened["findings"]}
    assert "burning sensation" in names

    typed = await authed_client.post(
        f"/api/v1/cases/{opened['id']}/turns",
        json={"text": "Both, but the right is worse."},
    )
    assert typed.status_code == 200, typed.text
    body = typed.json()
    nxt = body["current_question"]
    assert nxt is None or nxt["code"] != "q_laterality"
    last = body["turns"][-1]
    assert last["role"] == "system"
    assert "you have" not in last["text"].lower()


async def test_chat_turn_opens_case_without_writing_diagnosis(authed_client):
    created = await authed_client.post(
        "/api/v1/cases",
        json={"presenting_concern": "burning feet at night"},
    )
    case_id = created.json()["id"]
    resp = await authed_client.post(
        f"/api/v1/cases/{case_id}/turns",
        json={"text": "Also tingling in the toes."},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert any(t["role"] == "user" and "tingling" in t["text"].lower() for t in body["turns"])
    assert all(h["status"] == "open" for h in body["hypotheses"])
    assert "diagnosis" in body["disclaimer"].lower()


async def test_investigation_map_is_versioned_and_not_a_diagnosis(authed_client):
    created = await authed_client.post(
        "/api/v1/cases",
        json={
            "presenting_concern": (
                "For six months, my feet have burned at night. My doctor says my blood work is normal."
            )
        },
    )
    assert created.status_code == 201, created.text
    case_id = created.json()["id"]
    assert created.json()["map_version"] >= 1
    assert created.json()["confidence_increasers"]
    assert created.json()["memory_items"]
    mapped = await authed_client.get(f"/api/v1/cases/{case_id}/investigation-map")
    assert mapped.status_code == 200, mapped.text
    body = mapped.json()
    assert body["version"] >= 1
    assert body["not_disease_probability"] is True
    blob = json.dumps(body).lower()
    assert "you have small-fiber" not in blob
    turns = await authed_client.get(f"/api/v1/cases/{case_id}/turns")
    assert turns.status_code == 200
    assert turns.json()


async def test_case_requires_auth(client):
    resp = await client.post("/api/v1/cases", json={"presenting_concern": "fatigue"})
    assert resp.status_code == 401
