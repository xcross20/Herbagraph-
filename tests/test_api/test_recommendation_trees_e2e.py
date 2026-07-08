"""E2E API: one scenario per recommendation tree + stress cases through upload → report.

Ensures etiological, culture, autoimmune, allergy, pgx, nutritional, niche, and
kitchen-sink formats all produce actionable reports without unresolved abnormals.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.pipeline.lab_scenario_loader import list_scenarios, resolve_raw_path
from tests.test_api.e2e_helpers import (
    assert_no_unresolved_abnormal_biomarkers,
    generate_and_fetch_report,
    wait_for_lab_complete,
)

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]

SCENARIOS_ROOT = Path(__file__).resolve().parents[2] / "samples" / "lab_scenarios"

# One representative per tree / adversarial class — aligned with audit_pipeline_resilience.py
CRITICAL_SCENARIOS = [
    "signaling_inflammatory_quest",
    "etiological_h_pylori_urea_breath",
    "exposure_h_pylori_igg",
    "culture_urine_positive",
    "culture_sputum_positive",
    "etiological_hepatitis_b_surf_positive",
    "celiac_ttg_iga_positive",
    "allergy_peanut_ige_high",
    "pgx_cyp2d6_intermediate",
    "autoimmune_ana_positive",
    "nutritional_macrocytic_cbc",
    "niche_fecal_calprotectin_elevated",
    "format_healow_lipid_panel",
    "format_ocr_garbled_cbc",
    "kitchen_sink_quest_excerpt",
]


def _scenario_by_id(scenario_id: str) -> dict:
    for scenario in list_scenarios():
        if scenario["scenario_id"] == scenario_id:
            return scenario
    raise KeyError(scenario_id)


def _scenario_file(scenario_id: str) -> dict:
    scenario = _scenario_by_id(scenario_id)
    path = resolve_raw_path(scenario, SCENARIOS_ROOT)
    return {"file": (path.name, path.read_bytes(), "text/plain")}


def _expected_from_manifest(scenario_id: str) -> dict:
    expect = _scenario_by_id(scenario_id).get("expect", {})
    return {
        "must_include_recs": expect.get("recommendations", {}).get("must_include", []),
        "min_recs": expect.get("recommendations", {}).get("min_count", 0),
        "must_include_pathways": expect.get("pathways", {}).get("must_include", []),
        "min_abnormal": expect.get("routing", {}).get("min_abnormal", 0),
        "max_abnormal": expect.get("routing", {}).get("max_abnormal"),
        "primary_tree": expect.get("routing", {}).get("primary_tree"),
    }


@pytest.mark.parametrize("scenario_id", CRITICAL_SCENARIOS)
async def test_critical_scenario_e2e_upload_to_report(authed_client, scenario_id: str):
    """Full HTTP path for each recommendation tree representative."""
    upload_resp = await authed_client.post("/api/v1/labs/upload", files=_scenario_file(scenario_id))
    assert upload_resp.status_code == 201, upload_resp.text
    lab_report_id = upload_resp.json()["lab_report_id"]

    lab_body = await wait_for_lab_complete(authed_client, lab_report_id)
    assert lab_body["status"] == "complete", lab_body.get("error_message")

    min_rows = _scenario_by_id(scenario_id).get("expect", {}).get("parse", {}).get("min_rows", 1)
    assert len(lab_body.get("lab_results", [])) >= min_rows

    report_resp = await generate_and_fetch_report(authed_client, lab_report_id)
    body = report_resp.json()

    assert_no_unresolved_abnormal_biomarkers(body)

    expected = _expected_from_manifest(scenario_id)
    if expected["max_abnormal"] == 0:
        assert body["biomarker_summary"]["abnormal_count"] == 0
        return

    rec_names = {r["intervention_name"] for r in body["recommendations"]}
    for name in expected["must_include_recs"]:
        assert name in rec_names, f"{scenario_id}: missing recommendation {name!r}"

    if expected["min_recs"]:
        assert len(rec_names) >= expected["min_recs"]

    pathway_codes = {p["pathway_code"] for p in body["pathway_activations"]}
    for code in expected["must_include_pathways"]:
        assert code in pathway_codes, f"{scenario_id}: missing pathway {code!r}"