"""E2E API: Quest PDF F-column bleed (F HDL / F LDL) → catalog + recommendations."""

from unittest.mock import AsyncMock, patch

import pytest

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]

_F_PREFIX_LABS = (
    b"F HDL 48.0 L 60.00 - 180.00 (mg/dL)\n"
    b"F LDL Cholesterol Calc 142.00 H 0.00 - 99.00\n"
)


def _f_prefix_file():
    return {"file": ("f_prefix_lipids.txt", _F_PREFIX_LABS, "text/plain")}


async def _wait_for_lab_complete(client, lab_report_id: str, headers=None) -> None:
    for _ in range(50):
        resp = await client.get(f"/api/v1/labs/{lab_report_id}", headers=headers)
        assert resp.status_code == 200
        if resp.json().get("status") == "complete":
            return
    pytest.fail("lab processing did not complete in time")


async def _generate_and_fetch_report(client, lab_report_id: str, headers=None):
    resp = await client.post(f"/api/v1/reports/generate/{lab_report_id}", headers=headers)
    assert resp.status_code == 202, resp.text

    for _ in range(50):
        lab_resp = await client.get(f"/api/v1/labs/{lab_report_id}", headers=headers)
        assert lab_resp.status_code == 200
        lab = lab_resp.json()
        if lab.get("report_stage") == "complete" and lab.get("latest_report_id"):
            report_resp = await client.get(f"/api/v1/reports/{lab['latest_report_id']}", headers=headers)
            assert report_resp.status_code == 200
            return report_resp
    pytest.fail("report generation did not complete in time")


@patch("app.pipeline.evidence_retriever.search_europepmc", new_callable=AsyncMock)
@patch("app.pipeline.evidence_retriever.search_clinicaltrials", new_callable=AsyncMock)
@patch("app.pipeline.evidence_retriever.search_pubmed", new_callable=AsyncMock)
async def test_f_prefix_lipids_e2e_catalog_pathways_and_recommendations(
    mock_pubmed,
    mock_ct,
    mock_epmc,
    authed_client,
):
    """Upload F HDL / F LDL lines → persisted HDL+LDL → lipid pathways + recommendations."""
    mock_pubmed.return_value = []
    mock_ct.return_value = []
    mock_epmc.return_value = []

    upload_resp = await authed_client.post("/api/v1/labs/upload", files=_f_prefix_file())
    assert upload_resp.status_code == 201
    lab_report_id = upload_resp.json()["lab_report_id"]

    await _wait_for_lab_complete(authed_client, lab_report_id)

    lab_detail = await authed_client.get(f"/api/v1/labs/{lab_report_id}")
    persisted = {row["biomarker_name"] for row in lab_detail.json()["lab_results"]}
    assert persisted == {"HDL", "LDL"}, persisted

    report_resp = await _generate_and_fetch_report(authed_client, lab_report_id)
    body = report_resp.json()

    measured = body["biomarker_summary"]["measured_biomarkers"]
    unmatched = [
        m["biomarker_name"]
        for m in measured
        if m["status"] in ("low", "high", "critical_low", "critical_high") and not m["in_catalog"]
    ]
    assert unmatched == [], unmatched

    pathway_codes = {p["pathway_code"] for p in body["pathway_activations"]}
    assert "HEPATIC_LIPID" in pathway_codes

    systems = {s["system_code"]: s for s in body["biological_systems"]}
    assert systems["cardiovascular_risk"]["signal_level"] >= 2

    rec_names = {r["intervention_name"] for r in body["recommendations"]}
    assert len(rec_names) >= 1