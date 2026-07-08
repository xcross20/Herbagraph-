"""E2E API: stale persisted biomarker_name rows remap on regenerate.

Regression target: users who uploaded before alias fixes still have 'F HDL' /
'F LDL Cholesterol Calc' in the DB; Regenerate must remap without re-upload.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app import database
from app.models.lab import LabResult
from tests.test_api.e2e_helpers import (
    assert_no_unresolved_abnormal_biomarkers,
    assert_report_has_actionable_output,
    generate_and_fetch_report,
    wait_for_lab_complete,
)
from tests.test_api.test_f_prefix_lipids_e2e import _f_prefix_file

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


@patch("app.pipeline.evidence_retriever.search_europepmc", new_callable=AsyncMock)
@patch("app.pipeline.evidence_retriever.search_clinicaltrials", new_callable=AsyncMock)
@patch("app.pipeline.evidence_retriever.search_pubmed", new_callable=AsyncMock)
async def test_stale_persisted_f_prefix_rows_remap_on_regenerate(
    mock_pubmed,
    mock_ct,
    mock_epmc,
    authed_client,
):
    """Upload clean rows, corrupt names to pre-fix garbage, regenerate → catalog report."""
    mock_pubmed.return_value = []
    mock_ct.return_value = []
    mock_epmc.return_value = []

    upload_resp = await authed_client.post("/api/v1/labs/upload", files=_f_prefix_file())
    assert upload_resp.status_code == 201
    lab_report_id = upload_resp.json()["lab_report_id"]

    lab_body = await wait_for_lab_complete(authed_client, lab_report_id)
    assert lab_body["status"] == "complete"

    sync_session = database.get_sync_db()
    try:
        rows = sync_session.query(LabResult).filter_by(lab_report_id=lab_report_id).all()
        corrupt = {
            "HDL": "F HDL",
            "LDL": "F LDL Cholesterol Calc",
        }
        for row in rows:
            if row.biomarker_name in corrupt:
                row.biomarker_name = corrupt[row.biomarker_name]
        sync_session.commit()
    finally:
        sync_session.close()

    stale_detail = await authed_client.get(f"/api/v1/labs/{lab_report_id}")
    stale_names = {r["biomarker_name"] for r in stale_detail.json()["lab_results"]}
    assert stale_names == {"F HDL", "F LDL Cholesterol Calc"}, stale_names

    report_resp = await generate_and_fetch_report(authed_client, lab_report_id)
    body = report_resp.json()

    assert_no_unresolved_abnormal_biomarkers(body)
    assert_report_has_actionable_output(body)

    measured = {m["biomarker_name"]: m for m in body["biomarker_summary"]["measured_biomarkers"]}
    assert measured["HDL"]["in_catalog"] is True
    assert measured["LDL"]["in_catalog"] is True

    pathway_codes = {p["pathway_code"] for p in body["pathway_activations"]}
    assert "HEPATIC_LIPID" in pathway_codes