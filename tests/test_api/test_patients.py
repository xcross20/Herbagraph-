"""Tests for the Patient model/API (Phase 4 infrastructure: clinic mode)."""

import uuid

import pytest

pytestmark = pytest.mark.asyncio


async def test_create_patient_happy_path(authed_client):
    resp = await authed_client.post("/api/v1/patients", json={"age": 42, "biological_sex": "F"})
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["age"] == 42
    assert body["biological_sex"] == "F"
    assert "id" in body
    # No name or other identifying field is ever accepted or returned.
    assert "name" not in body


async def test_create_patient_with_no_fields(authed_client):
    resp = await authed_client.post("/api/v1/patients", json={})
    assert resp.status_code == 201, resp.text
    assert resp.json()["age"] is None


async def test_create_patient_requires_auth(client):
    resp = await client.post("/api/v1/patients", json={"age": 30})
    assert resp.status_code == 401


async def test_list_patients_only_returns_current_users_patients(client, db_session):
    from app.core.security import create_access_token
    from app.models.user import HealthProfile, User

    user_a = User(email="a@example.com", hashed_password="x")
    user_b = User(email="b@example.com", hashed_password="x")
    db_session.add_all([user_a, user_b])
    await db_session.flush()
    db_session.add_all([HealthProfile(user_id=user_a.id), HealthProfile(user_id=user_b.id)])
    await db_session.commit()

    headers_a = {"Authorization": f"Bearer {create_access_token(str(user_a.id))}"}
    headers_b = {"Authorization": f"Bearer {create_access_token(str(user_b.id))}"}

    await client.post("/api/v1/patients", json={"age": 25}, headers=headers_a)
    await client.post("/api/v1/patients", json={"age": 60}, headers=headers_b)

    resp_a = await client.get("/api/v1/patients", headers=headers_a)
    assert resp_a.status_code == 200
    assert len(resp_a.json()) == 1
    assert resp_a.json()[0]["age"] == 25


async def test_get_patient_404_for_other_users_patient(client, db_session):
    from app.core.security import create_access_token
    from app.models.user import HealthProfile, User

    owner = User(email="owner@example.com", hashed_password="x")
    intruder = User(email="intruder@example.com", hashed_password="x")
    db_session.add_all([owner, intruder])
    await db_session.flush()
    db_session.add_all([HealthProfile(user_id=owner.id), HealthProfile(user_id=intruder.id)])
    await db_session.commit()

    owner_headers = {"Authorization": f"Bearer {create_access_token(str(owner.id))}"}
    intruder_headers = {"Authorization": f"Bearer {create_access_token(str(intruder.id))}"}

    create_resp = await client.post("/api/v1/patients", json={"age": 50}, headers=owner_headers)
    patient_id = create_resp.json()["id"]

    resp = await client.get(f"/api/v1/patients/{patient_id}", headers=intruder_headers)
    assert resp.status_code == 404


async def test_get_patient_404_for_nonexistent_id(authed_client):
    resp = await authed_client.get(f"/api/v1/patients/{uuid.uuid4()}")
    assert resp.status_code == 404


async def test_delete_patient_removes_it(authed_client):
    create_resp = await authed_client.post("/api/v1/patients", json={"age": 33})
    patient_id = create_resp.json()["id"]

    delete_resp = await authed_client.delete(f"/api/v1/patients/{patient_id}")
    assert delete_resp.status_code == 204

    get_resp = await authed_client.get(f"/api/v1/patients/{patient_id}")
    assert get_resp.status_code == 404


async def test_upload_lab_report_with_valid_patient_id(authed_client):
    patient_resp = await authed_client.post("/api/v1/patients", json={"age": 40})
    patient_id = patient_resp.json()["id"]

    files = {"file": ("labs.txt", b"CRP   8.2  mg/L  (0.0-3.0)\n", "text/plain")}
    resp = await authed_client.post(
        "/api/v1/labs/upload", files=files, data={"patient_id": patient_id}
    )
    assert resp.status_code == 201, resp.text


async def test_upload_lab_report_with_unknown_patient_id_404s(authed_client):
    files = {"file": ("labs.txt", b"CRP   8.2  mg/L  (0.0-3.0)\n", "text/plain")}
    resp = await authed_client.post(
        "/api/v1/labs/upload", files=files, data={"patient_id": str(uuid.uuid4())}
    )
    assert resp.status_code == 404


async def test_upload_lab_report_without_patient_id_still_works(authed_client):
    files = {"file": ("labs.txt", b"CRP   8.2  mg/L  (0.0-3.0)\n", "text/plain")}
    resp = await authed_client.post("/api/v1/labs/upload", files=files)
    assert resp.status_code == 201, resp.text
