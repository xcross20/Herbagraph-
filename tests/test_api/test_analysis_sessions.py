import uuid
from unittest.mock import patch

import pytest

from app.config import settings

pytestmark = pytest.mark.asyncio

VALID_LAB_TEXT = (
    b"CRP                    8.20  mg/L   (0.00-3.00)\n"
    b"Glucose                95.00  mg/dL   (70.00-99.00)\n"
)

VALID_LAB_TEXT_B = (
    b"LDL Cholesterol        140.00 mg/dL  (0.00-100.00)\n"
    b"HDL Cholesterol         45.00 mg/dL  (40.00-60.00)\n"
)


def _lab_file(content: bytes, filename: str):
    return ("files", (filename, content, "text/plain"))


async def test_create_analysis_session(authed_client):
    resp = await authed_client.post(
        "/api/v1/analysis-sessions",
        json={"title": "My Integrated Session"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["title"] == "My Integrated Session"
    assert body["status"] == "pending"
    assert body["lab_reports"] == []


async def test_create_requires_auth(client):
    resp = await client.post("/api/v1/analysis-sessions", json={"title": "x"})
    assert resp.status_code == 401


async def test_upload_multiple_files_to_session(authed_client):
    create = await authed_client.post("/api/v1/analysis-sessions", json={})
    assert create.status_code == 201
    session_id = create.json()["id"]

    resp = await authed_client.post(
        f"/api/v1/analysis-sessions/{session_id}/upload",
        files=[
            _lab_file(VALID_LAB_TEXT, "cbc.txt"),
            _lab_file(VALID_LAB_TEXT_B, "lipids.txt"),
        ],
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["analysis_session_id"] == session_id
    assert len(body["uploaded"]) == 2

    get_resp = await authed_client.get(f"/api/v1/analysis-sessions/{session_id}")
    assert get_resp.status_code == 200
    session = get_resp.json()
    assert len(session["lab_reports"]) == 2


async def test_run_requires_at_least_two_lab_reports(authed_client):
    create = await authed_client.post("/api/v1/analysis-sessions", json={})
    session_id = create.json()["id"]

    resp = await authed_client.post(f"/api/v1/analysis-sessions/{session_id}/run")
    assert resp.status_code == 409
    assert "two" in resp.json()["detail"].lower()


@patch("app.workers.tasks.run_integrated_analysis")
async def test_run_integrated_analysis_accepts_request(mock_run, authed_client):
    mock_run.return_value = {"status": "complete", "report_id": str(uuid.uuid4())}

    create = await authed_client.post("/api/v1/analysis-sessions", json={})
    session_id = create.json()["id"]

    upload = await authed_client.post(
        f"/api/v1/analysis-sessions/{session_id}/upload",
        files=[
            _lab_file(VALID_LAB_TEXT, "cbc.txt"),
            _lab_file(VALID_LAB_TEXT_B, "lipids.txt"),
        ],
    )
    assert upload.status_code == 201

    resp = await authed_client.post(f"/api/v1/analysis-sessions/{session_id}/run")
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["analysis_session_id"] == session_id
    assert body["task_id"]
    mock_run.assert_called_once()


async def test_upload_rejects_unsupported_extension(authed_client):
    create = await authed_client.post("/api/v1/analysis-sessions", json={})
    session_id = create.json()["id"]

    resp = await authed_client.post(
        f"/api/v1/analysis-sessions/{session_id}/upload",
        files=[("files", ("bad.exe", b"x", "application/octet-stream"))],
    )
    assert resp.status_code == 400


async def test_upload_rejects_oversized_file(authed_client, monkeypatch):
    monkeypatch.setattr(settings, "max_file_size_mb", 0)
    create = await authed_client.post("/api/v1/analysis-sessions", json={})
    session_id = create.json()["id"]

    resp = await authed_client.post(
        f"/api/v1/analysis-sessions/{session_id}/upload",
        files=[_lab_file(b"x" * 2048, "big.txt")],
    )
    assert resp.status_code == 413