import uuid
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.asyncio

VALID_LAB_TEXT = (
    b"CRP                    8.20  mg/L   (0.00-3.00)\n"
    b"Glucose                95.00  mg/dL   (70.00-99.00)\n"
)


async def _upload_lab(authed_client, filename: str) -> str:
    resp = await authed_client.post(
        "/api/v1/labs/upload",
        files={"file": (filename, VALID_LAB_TEXT, "text/plain")},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["lab_report_id"]


@patch("app.workers.tasks.run_integrated_analysis")
async def test_link_existing_labs_to_session(mock_run, authed_client):
    mock_run.return_value = {"status": "complete", "report_id": str(uuid.uuid4())}

    lab_a = await _upload_lab(authed_client, "cbc.txt")
    lab_b = await _upload_lab(authed_client, "cmp.txt")

    create = await authed_client.post("/api/v1/analysis-sessions", json={"title": "Link test"})
    session_id = create.json()["id"]

    link = await authed_client.post(
        f"/api/v1/analysis-sessions/{session_id}/link-labs",
        json={"lab_report_ids": [lab_a, lab_b]},
    )
    assert link.status_code == 200, link.text
    assert len(link.json()["lab_reports"]) == 2

    run = await authed_client.post(f"/api/v1/analysis-sessions/{session_id}/run")
    assert run.status_code == 202