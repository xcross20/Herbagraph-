"""E2E API contract: macrocytic CBC upload → report → systems + recommendations."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]

_SCENARIO_PATH = (
    Path(__file__).resolve().parents[2]
    / "samples"
    / "lab_scenarios"
    / "raw"
    / "nutritional_macrocytic_cbc.txt"
)
_MACROCYTIC_CBC = _SCENARIO_PATH.read_bytes()

_EXPECTED_NUTRIENTS = {"B12", "Folate", "Iron"}


def _macrocytic_file():
    return {"file": ("macrocytic_cbc.txt", _MACROCYTIC_CBC, "text/plain")}


async def _wait_for_lab_complete(client, lab_report_id: str, headers=None) -> None:
    for _ in range(50):
        resp = await client.get(f"/api/v1/labs/{lab_report_id}", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        if body.get("status") == "complete":
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
async def test_macrocytic_cbc_e2e_nutrient_systems_and_recommendations(
    mock_pubmed,
    mock_ct,
    mock_epmc,
    authed_client,
):
    """Upload mean-cell CBC → Nutrient Status signal + B12/Folate/Iron recommendations."""
    mock_pubmed.return_value = []
    mock_ct.return_value = []
    mock_epmc.return_value = []

    upload_resp = await authed_client.post("/api/v1/labs/upload", files=_macrocytic_file())
    assert upload_resp.status_code == 201
    lab_report_id = upload_resp.json()["lab_report_id"]

    await _wait_for_lab_complete(authed_client, lab_report_id)

    lab_detail = await authed_client.get(f"/api/v1/labs/{lab_report_id}")
    assert lab_detail.status_code == 200
    persisted_names = {row["biomarker_name"] for row in lab_detail.json()["lab_results"]}
    assert {"MCH", "MCV", "RDW"}.issubset(persisted_names)

    report_resp = await _generate_and_fetch_report(authed_client, lab_report_id)
    body = report_resp.json()

    systems_by_code = {s["system_code"]: s for s in body["biological_systems"]}
    assert "nutrient_status" in systems_by_code
    nutrient = systems_by_code["nutrient_status"]
    assert nutrient["signal_level"] >= 2, nutrient
    assert nutrient["direction"] in ("reduced", "mixed", "elevated")

    rec_names = {r["intervention_name"] for r in body["recommendations"]}
    assert _EXPECTED_NUTRIENTS.issubset(rec_names), rec_names

    assert body["pathway_activations"]
    pathway_codes = {p["pathway_code"] for p in body["pathway_activations"]}
    assert "ONE_CARBON_METHYLATION" in pathway_codes
    assert "IRON_HEPCIDIN" in pathway_codes