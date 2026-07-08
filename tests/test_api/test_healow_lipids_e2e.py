"""E2E API: Healow/eClinicalWorks lipid panel → catalog + pathways + recommendations.

Regression target: SLICE-110 (.strip() crash), <= ranges, F-column prefixes,
and 'Cholesterol, Total' comma-suffix ambiguity.
"""

from pathlib import Path

import pytest

from tests.test_api.e2e_helpers import (
    assert_no_unresolved_abnormal_biomarkers,
    assert_report_has_actionable_output,
    generate_and_fetch_report,
    wait_for_lab_complete,
)

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]

_EXCERPT = Path(__file__).resolve().parents[1] / "fixtures" / "healow_lipid_panel_excerpt.txt"
_EXPECTED_CATALOG_NAMES = {
    "Total Cholesterol",
    "Triglycerides",
    "HDL",
    "LDL",
    "Non-HDL Cholesterol",
    "Chol/HDL Ratio",
}


def _healow_file():
    return {"file": ("healow_lipids.txt", _EXCERPT.read_bytes(), "text/plain")}


async def test_healow_lipids_e2e_full_pipeline_no_evidence_mocks(authed_client):
    """Upload → worker parse/normalize → report without mocking evidence or LLM."""
    upload_resp = await authed_client.post("/api/v1/labs/upload", files=_healow_file())
    assert upload_resp.status_code == 201, upload_resp.text
    lab_report_id = upload_resp.json()["lab_report_id"]

    lab_body = await wait_for_lab_complete(authed_client, lab_report_id)
    assert lab_body["status"] == "complete", lab_body.get("error_message")

    persisted = {row["biomarker_name"] for row in lab_body["lab_results"]}
    assert persisted == _EXPECTED_CATALOG_NAMES, persisted

    report_resp = await generate_and_fetch_report(authed_client, lab_report_id)
    body = report_resp.json()

    assert_no_unresolved_abnormal_biomarkers(body)
    assert_report_has_actionable_output(body, min_recommendations=1)

    pathway_codes = {p["pathway_code"] for p in body["pathway_activations"]}
    assert "HEPATIC_LIPID" in pathway_codes

    systems = {s["system_code"]: s for s in body["biological_systems"]}
    assert systems["cardiovascular_risk"]["signal_level"] >= 2