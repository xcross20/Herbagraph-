"""Typed labs enter the same normalizer and never open a file parser."""

from __future__ import annotations

import pytest

from app.workers.tasks import process_lab_report

pytestmark = pytest.mark.asyncio


async def test_manual_entry_normalizes_and_skips_file_parse(authed_client):
    created = await authed_client.post(
        "/api/v1/labs/manual",
        json={
            "results": [
                {
                    "name": "LDL Cholesterol",
                    "value": 160,
                    "unit": "mg/dL",
                    "reference_range_low": 0,
                    "reference_range_high": 100,
                }
            ]
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["original_filename"] == "manual-entry"
    assert body["status"] == "complete"
    assert body["lab_results"][0]["biomarker_name"]
    assert body["lab_results"][0]["value"] == 160

    parsed = process_lab_report(body["id"])
    assert parsed["skipped_parse"] is True
    assert parsed["biomarker_count"] == 1

    again = await authed_client.get(f"/api/v1/labs/{body['id']}")
    assert again.status_code == 200
    assert again.json()["status"] == "complete"
    assert again.json()["lab_results"][0]["value"] == 160


async def test_manual_entry_rejects_empty_grid(authed_client):
    resp = await authed_client.post("/api/v1/labs/manual", json={"results": []})
    assert resp.status_code == 400


async def test_manual_patch_replaces_values(authed_client):
    created = await authed_client.post(
        "/api/v1/labs/manual",
        json={"results": [{"name": "Glucose", "value": 90, "unit": "mg/dL"}]},
    )
    assert created.status_code == 201, created.text
    lab_id = created.json()["id"]
    patched = await authed_client.patch(
        f"/api/v1/labs/{lab_id}/results",
        json={"results": [{"name": "Glucose", "value": 140, "unit": "mg/dL"}]},
    )
    assert patched.status_code == 200, patched.text
    values = [row["value"] for row in patched.json()["lab_results"]]
    assert values == [140.0]
