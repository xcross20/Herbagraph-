import uuid

import pytest

from app.config import settings

pytestmark = pytest.mark.asyncio

VALID_LAB_TEXT = (
    b"CRP                    8.20  mg/L   (0.00-3.00)\n"
    b"Glucose                95.00  mg/dL   (70.00-99.00)\n"
)


def _lab_file(content: bytes = VALID_LAB_TEXT, filename: str = "labs.txt"):
    return {"file": (filename, content, "text/plain")}


# ---------------------------------------------------------------------------
# upload
# ---------------------------------------------------------------------------


async def test_upload_happy_path_returns_201(authed_client):
    resp = await authed_client.post("/api/v1/labs/upload", files=_lab_file())
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert "lab_report_id" in body
    assert uuid.UUID(body["lab_report_id"])
    assert "task_id" in body and body["task_id"]
    assert body["message"]
    assert body["status"] == "processing"


async def test_upload_saves_file_with_lab_report_id_not_none(authed_client):
    import os

    from app.config import settings

    resp = await authed_client.post("/api/v1/labs/upload", files=_lab_file())
    assert resp.status_code == 201, resp.text
    lab_report_id = resp.json()["lab_report_id"]

    get_resp = await authed_client.get(f"/api/v1/labs/{lab_report_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["status"] == "complete"

    stored_names = os.listdir(settings.upload_dir)
    assert stored_names
    assert not any("None" in name for name in stored_names)
    assert any(lab_report_id in name for name in stored_names)


async def test_upload_unsupported_extension_returns_400(authed_client):
    resp = await authed_client.post(
        "/api/v1/labs/upload", files={"file": ("labs.exe", b"whatever", "application/octet-stream")}
    )
    assert resp.status_code == 400
    assert "unsupported" in resp.json()["detail"].lower()


async def test_upload_oversized_file_returns_413(authed_client, monkeypatch):
    monkeypatch.setattr(settings, "max_file_size_mb", 0)
    resp = await authed_client.post("/api/v1/labs/upload", files=_lab_file(b"x" * 1024))
    assert resp.status_code == 413
    assert "exceeds" in resp.json()["detail"].lower()


async def test_upload_requires_auth(client):
    resp = await client.post("/api/v1/labs/upload", files=_lab_file())
    assert resp.status_code == 401


async def test_upload_csv_extension_accepted(authed_client):
    resp = await authed_client.post(
        "/api/v1/labs/upload", files=_lab_file(b"CRP,8.20,mg/L,0,3\n", filename="labs.csv")
    )
    assert resp.status_code == 201, resp.text


async def test_upload_empty_file_completes_with_zero_results(authed_client):
    resp = await authed_client.post("/api/v1/labs/upload", files=_lab_file(b""))
    assert resp.status_code == 201
    lab_report_id = resp.json()["lab_report_id"]

    get_resp = await authed_client.get(f"/api/v1/labs/{lab_report_id}")
    assert get_resp.status_code == 200
    body = get_resp.json()
    assert body["status"] == "complete"
    assert body["lab_results"] == []


async def test_upload_then_processing_completes_with_lab_results(authed_client):
    upload_resp = await authed_client.post("/api/v1/labs/upload", files=_lab_file())
    assert upload_resp.status_code == 201
    lab_report_id = upload_resp.json()["lab_report_id"]

    get_resp = await authed_client.get(f"/api/v1/labs/{lab_report_id}")
    assert get_resp.status_code == 200
    body = get_resp.json()
    assert body["status"] == "complete"
    assert body["error_message"] is None
    assert len(body["lab_results"]) == 2

    by_name = {r["biomarker_name"]: r for r in body["lab_results"]}
    assert "CRP" in by_name
    assert by_name["CRP"]["value"] == 8.2
    assert by_name["CRP"]["status"] == "high"
    assert "Glucose" in by_name
    assert by_name["Glucose"]["status"] in ("normal", "optimal")


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


async def test_list_lab_reports_only_returns_current_users_reports(client, db_session):
    from app.core.security import create_access_token
    from app.models.user import HealthProfile, User

    user_a = User(email="labs-a@example.com", hashed_password="x", is_active=True, is_verified=True)
    user_b = User(email="labs-b@example.com", hashed_password="x", is_active=True, is_verified=True)
    db_session.add_all([user_a, user_b])
    await db_session.flush()
    db_session.add(HealthProfile(user_id=user_a.id))
    db_session.add(HealthProfile(user_id=user_b.id))
    await db_session.commit()

    headers_a = {"Authorization": f"Bearer {create_access_token(str(user_a.id))}"}
    headers_b = {"Authorization": f"Bearer {create_access_token(str(user_b.id))}"}

    upload_a = await client.post("/api/v1/labs/upload", files=_lab_file(), headers=headers_a)
    assert upload_a.status_code == 201
    upload_b = await client.post("/api/v1/labs/upload", files=_lab_file(), headers=headers_b)
    assert upload_b.status_code == 201

    list_a = await client.get("/api/v1/labs", headers=headers_a)
    assert list_a.status_code == 200
    ids_a = {r["id"] for r in list_a.json()}
    assert ids_a == {upload_a.json()["lab_report_id"]}

    list_b = await client.get("/api/v1/labs", headers=headers_b)
    assert list_b.status_code == 200
    ids_b = {r["id"] for r in list_b.json()}
    assert ids_b == {upload_b.json()["lab_report_id"]}


async def test_list_lab_reports_requires_auth(client):
    resp = await client.get("/api/v1/labs")
    assert resp.status_code == 401


async def test_list_lab_reports_empty_for_new_user(authed_client):
    resp = await authed_client.get("/api/v1/labs")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_lab_reports_summary_shape_omits_lab_results(authed_client):
    await authed_client.post("/api/v1/labs/upload", files=_lab_file())
    resp = await authed_client.get("/api/v1/labs")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert "lab_results" not in body[0]
    assert set(body[0].keys()) == {
        "id",
        "patient_id",
        "original_filename",
        "status",
        "report_stage",
        "latest_report_id",
        "error_message",
        "created_at",
    }


async def test_list_lab_reports_multiple_uploads_all_present(authed_client):
    await authed_client.post("/api/v1/labs/upload", files=_lab_file(filename="a.txt"))
    await authed_client.post("/api/v1/labs/upload", files=_lab_file(filename="b.txt"))
    resp = await authed_client.get("/api/v1/labs")
    assert resp.status_code == 200
    filenames = {r["original_filename"] for r in resp.json()}
    assert filenames == {"a.txt", "b.txt"}


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------


async def test_get_lab_report_404_for_nonexistent_id(authed_client):
    resp = await authed_client.get(f"/api/v1/labs/{uuid.uuid4()}")
    assert resp.status_code == 404


async def test_get_lab_report_404_for_other_users_report(client, db_session):
    from app.core.security import create_access_token
    from app.models.user import HealthProfile, User

    owner = User(email="owner@example.com", hashed_password="x", is_active=True, is_verified=True)
    intruder = User(email="intruder@example.com", hashed_password="x", is_active=True, is_verified=True)
    db_session.add_all([owner, intruder])
    await db_session.flush()
    db_session.add(HealthProfile(user_id=owner.id))
    db_session.add(HealthProfile(user_id=intruder.id))
    await db_session.commit()

    owner_headers = {"Authorization": f"Bearer {create_access_token(str(owner.id))}"}
    intruder_headers = {"Authorization": f"Bearer {create_access_token(str(intruder.id))}"}

    upload = await client.post("/api/v1/labs/upload", files=_lab_file(), headers=owner_headers)
    lab_report_id = upload.json()["lab_report_id"]

    resp = await client.get(f"/api/v1/labs/{lab_report_id}", headers=intruder_headers)
    assert resp.status_code == 404


async def test_get_lab_report_requires_auth(client):
    resp = await client.get(f"/api/v1/labs/{uuid.uuid4()}")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


async def test_delete_lab_report_removes_it(authed_client):
    upload = await authed_client.post("/api/v1/labs/upload", files=_lab_file())
    lab_report_id = upload.json()["lab_report_id"]

    delete_resp = await authed_client.delete(f"/api/v1/labs/{lab_report_id}")
    assert delete_resp.status_code == 204

    get_resp = await authed_client.get(f"/api/v1/labs/{lab_report_id}")
    assert get_resp.status_code == 404


async def test_delete_lab_report_with_linked_session_rows(authed_client, db_session):
    """Labs linked into analysis sessions must still be deletable (cascade dependents)."""
    from app.models.analysis_session import AnalysisSession, AnalysisSessionLabReport
    from app.models.enums import AnalysisSessionStatus, AnalysisType
    from app.models.lab import LabReport
    from sqlalchemy import select

    upload = await authed_client.post("/api/v1/labs/upload", files=_lab_file())
    assert upload.status_code == 201
    lab_report_id = upload.json()["lab_report_id"]

    me = await authed_client.get("/api/v1/auth/me")
    user_id = me.json()["id"]

    # Attach session link via ORM (simulates integrated analysis)
    lab = (
        await db_session.execute(select(LabReport).where(LabReport.id == lab_report_id))
    ).scalar_one()
    session = AnalysisSession(
        user_id=user_id,
        patient_id=lab.patient_id,
        title="Test session",
        analysis_type=AnalysisType.MULTI_REPORT_SNAPSHOT,
        status=AnalysisSessionStatus.COMPLETE,
    )
    db_session.add(session)
    await db_session.flush()
    db_session.add(
        AnalysisSessionLabReport(
            analysis_session_id=session.id,
            lab_report_id=lab.id,
            panel_label="CBC",
        )
    )
    await db_session.commit()

    delete_resp = await authed_client.delete(f"/api/v1/labs/{lab_report_id}")
    assert delete_resp.status_code == 204, delete_resp.text
    get_resp = await authed_client.get(f"/api/v1/labs/{lab_report_id}")
    assert get_resp.status_code == 404


async def test_download_lab_file_returns_original_bytes(authed_client):
    content = b"CRP    8.20  mg/L   (0.00-3.00)\n"
    upload = await authed_client.post(
        "/api/v1/labs/upload",
        files={"file": ("demo_lab.txt", content, "text/plain")},
    )
    assert upload.status_code == 201
    lab_report_id = upload.json()["lab_report_id"]

    resp = await authed_client.get(f"/api/v1/labs/{lab_report_id}/download")
    assert resp.status_code == 200
    assert resp.content == content
    assert "attachment" in (resp.headers.get("content-disposition") or "").lower()
    assert "demo_lab.txt" in (resp.headers.get("content-disposition") or "")


async def test_download_lab_file_requires_auth(client):
    resp = await client.get(f"/api/v1/labs/{uuid.uuid4()}/download")
    assert resp.status_code == 401


async def test_download_lab_file_404_for_nonexistent_id(authed_client):
    resp = await authed_client.get(f"/api/v1/labs/{uuid.uuid4()}/download")
    assert resp.status_code == 404


async def test_delete_lab_report_404_for_nonexistent_id(authed_client):
    resp = await authed_client.delete(f"/api/v1/labs/{uuid.uuid4()}")
    assert resp.status_code == 404


async def test_delete_lab_report_requires_auth(client):
    resp = await client.delete(f"/api/v1/labs/{uuid.uuid4()}")
    assert resp.status_code == 401
