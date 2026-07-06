import uuid

import pytest

from app.models.enums import LabReportStatus
from app.models.lab import LabReport

pytestmark = pytest.mark.asyncio

VALID_LAB_TEXT_BASELINE = b"CRP                    8.20  mg/L   (0.00-3.00)\n"
VALID_LAB_TEXT_FOLLOW_UP = b"CRP                    1.50  mg/L   (0.00-3.00)\n"


def _lab_file(content, name="labs.txt"):
    return {"file": (name, content, "text/plain")}


async def _upload(authed_client, content, name="labs.txt") -> str:
    resp = await authed_client.post("/api/v1/labs/upload", files=_lab_file(content, name))
    assert resp.status_code == 201, resp.text
    return resp.json()["lab_report_id"]


async def _create_tracking(authed_client, baseline_id: str, intervention_name: str = "Curcumin") -> dict:
    resp = await authed_client.post(
        "/api/v1/tracking", json={"intervention_name": intervention_name, "baseline_lab_report_id": baseline_id}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_create_tracking_success(authed_client):
    baseline_id = await _upload(authed_client, VALID_LAB_TEXT_BASELINE)
    tracking = await _create_tracking(authed_client, baseline_id)
    assert tracking["intervention_name"] == "Curcumin"
    assert tracking["baseline_lab_report_id"] == baseline_id
    assert tracking["follow_up_lab_report_id"] is None


async def test_create_tracking_404_for_nonexistent_baseline(authed_client):
    resp = await authed_client.post(
        "/api/v1/tracking",
        json={"intervention_name": "Curcumin", "baseline_lab_report_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 404


async def test_create_tracking_409_if_baseline_not_complete(authed_client, db_session, test_user):
    lab_report = LabReport(
        user_id=test_user.id,
        original_filename="pending.txt",
        encrypted_file_path="",
        file_size_bytes=10,
        status=LabReportStatus.PENDING,
    )
    db_session.add(lab_report)
    await db_session.commit()
    await db_session.refresh(lab_report)

    resp = await authed_client.post(
        "/api/v1/tracking",
        json={"intervention_name": "Curcumin", "baseline_lab_report_id": str(lab_report.id)},
    )
    assert resp.status_code == 409


async def test_create_tracking_requires_auth(client):
    resp = await client.post(
        "/api/v1/tracking",
        json={"intervention_name": "Curcumin", "baseline_lab_report_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 401


async def test_list_tracking_returns_only_own_records(client, db_session):
    from app.core.security import create_access_token
    from app.models.user import HealthProfile, User

    owner = User(email="track-owner@example.com", hashed_password="x", is_active=True, is_verified=True)
    other = User(email="track-other@example.com", hashed_password="x", is_active=True, is_verified=True)
    db_session.add_all([owner, other])
    await db_session.flush()
    db_session.add(HealthProfile(user_id=owner.id))
    db_session.add(HealthProfile(user_id=other.id))
    await db_session.commit()

    owner_headers = {"Authorization": f"Bearer {create_access_token(str(owner.id))}"}
    other_headers = {"Authorization": f"Bearer {create_access_token(str(other.id))}"}

    upload = await client.post("/api/v1/labs/upload", files=_lab_file(VALID_LAB_TEXT_BASELINE), headers=owner_headers)
    baseline_id = upload.json()["lab_report_id"]
    await client.post(
        "/api/v1/tracking",
        json={"intervention_name": "Curcumin", "baseline_lab_report_id": baseline_id},
        headers=owner_headers,
    )

    owner_list = await client.get("/api/v1/tracking", headers=owner_headers)
    other_list = await client.get("/api/v1/tracking", headers=other_headers)
    assert len(owner_list.json()) == 1
    assert other_list.json() == []


async def test_get_tracking_404_for_other_users_record(client, db_session):
    from app.core.security import create_access_token
    from app.models.user import HealthProfile, User

    owner = User(email="track-owner2@example.com", hashed_password="x", is_active=True, is_verified=True)
    intruder = User(email="track-intruder2@example.com", hashed_password="x", is_active=True, is_verified=True)
    db_session.add_all([owner, intruder])
    await db_session.flush()
    db_session.add(HealthProfile(user_id=owner.id))
    db_session.add(HealthProfile(user_id=intruder.id))
    await db_session.commit()

    owner_headers = {"Authorization": f"Bearer {create_access_token(str(owner.id))}"}
    intruder_headers = {"Authorization": f"Bearer {create_access_token(str(intruder.id))}"}

    upload = await client.post("/api/v1/labs/upload", files=_lab_file(VALID_LAB_TEXT_BASELINE), headers=owner_headers)
    baseline_id = upload.json()["lab_report_id"]
    created = await client.post(
        "/api/v1/tracking",
        json={"intervention_name": "Curcumin", "baseline_lab_report_id": baseline_id},
        headers=owner_headers,
    )
    tracking_id = created.json()["id"]

    resp = await client.get(f"/api/v1/tracking/{tracking_id}", headers=intruder_headers)
    assert resp.status_code == 404


async def test_delete_tracking(authed_client):
    baseline_id = await _upload(authed_client, VALID_LAB_TEXT_BASELINE)
    tracking = await _create_tracking(authed_client, baseline_id)
    resp = await authed_client.delete(f"/api/v1/tracking/{tracking['id']}")
    assert resp.status_code == 204
    resp = await authed_client.get(f"/api/v1/tracking/{tracking['id']}")
    assert resp.status_code == 404


async def test_attach_follow_up_success(authed_client):
    baseline_id = await _upload(authed_client, VALID_LAB_TEXT_BASELINE, "baseline.txt")
    follow_up_id = await _upload(authed_client, VALID_LAB_TEXT_FOLLOW_UP, "followup.txt")
    tracking = await _create_tracking(authed_client, baseline_id)

    resp = await authed_client.post(
        f"/api/v1/tracking/{tracking['id']}/follow-up", json={"follow_up_lab_report_id": follow_up_id}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["follow_up_lab_report_id"] == follow_up_id


async def test_attach_follow_up_409_if_same_as_baseline(authed_client):
    baseline_id = await _upload(authed_client, VALID_LAB_TEXT_BASELINE)
    tracking = await _create_tracking(authed_client, baseline_id)

    resp = await authed_client.post(
        f"/api/v1/tracking/{tracking['id']}/follow-up", json={"follow_up_lab_report_id": baseline_id}
    )
    assert resp.status_code == 409


async def test_get_response_409_without_follow_up(authed_client):
    baseline_id = await _upload(authed_client, VALID_LAB_TEXT_BASELINE)
    tracking = await _create_tracking(authed_client, baseline_id)

    resp = await authed_client.get(f"/api/v1/tracking/{tracking['id']}/response")
    assert resp.status_code == 409


async def test_get_response_report_shape_and_disclaimer(authed_client):
    baseline_id = await _upload(authed_client, VALID_LAB_TEXT_BASELINE, "baseline.txt")
    follow_up_id = await _upload(authed_client, VALID_LAB_TEXT_FOLLOW_UP, "followup.txt")
    tracking = await _create_tracking(authed_client, baseline_id)
    await authed_client.post(
        f"/api/v1/tracking/{tracking['id']}/follow-up", json={"follow_up_lab_report_id": follow_up_id}
    )

    resp = await authed_client.get(f"/api/v1/tracking/{tracking['id']}/response")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["intervention_name"] == "Curcumin"
    assert "does not infer causality" in body["disclaimer"]
    assert body["biomarker_changes"][0]["biomarker_name"] == "CRP"
    assert body["biomarker_changes"][0]["direction"] == "improved"
    inflammation = next(s for s in body["system_responses"] if s["system_code"] == "inflammation")
    assert inflammation["response"] == "improved"
