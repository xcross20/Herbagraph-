"""Shared helpers for API-level end-to-end integration tests."""

from __future__ import annotations

import pytest


async def wait_for_lab_complete(client, lab_report_id: str, *, headers=None, max_polls: int = 50) -> dict:
    """Poll until lab processing finishes; return the final lab detail JSON."""
    for _ in range(max_polls):
        resp = await client.get(f"/api/v1/labs/{lab_report_id}", headers=headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        status = body.get("status")
        if status in ("complete", "failed"):
            return body
    pytest.fail("lab processing did not complete in time")


async def generate_and_fetch_report(client, lab_report_id: str, *, headers=None, max_polls: int = 50):
    """Trigger report generation and poll until report_stage=complete."""
    resp = await client.post(f"/api/v1/reports/generate/{lab_report_id}", headers=headers)
    assert resp.status_code == 202, resp.text

    for _ in range(max_polls):
        lab_resp = await client.get(f"/api/v1/labs/{lab_report_id}", headers=headers)
        assert lab_resp.status_code == 200
        lab = lab_resp.json()
        stage = lab.get("report_stage")
        if stage == "failed":
            pytest.fail(f"report generation failed: {lab.get('report_error_message')}")
        if stage == "complete" and lab.get("latest_report_id"):
            report_resp = await client.get(f"/api/v1/reports/{lab['latest_report_id']}", headers=headers)
            assert report_resp.status_code == 200
            return report_resp
    pytest.fail("report generation did not complete in time")


def assert_no_unresolved_abnormal_biomarkers(report_body: dict) -> None:
    """Abnormal rows must resolve to catalog biomarkers — the #1 UI blindspot."""
    measured = report_body["biomarker_summary"]["measured_biomarkers"]
    unmatched = [
        m["biomarker_name"]
        for m in measured
        if m["status"] in ("low", "high", "critical_low", "critical_high") and not m["in_catalog"]
    ]
    assert unmatched == [], f"unresolved abnormal biomarkers: {unmatched}"


def assert_report_has_actionable_output(report_body: dict, *, min_recommendations: int = 1) -> None:
    """Report must surface pathways, systems, and at least one recommendation."""
    assert report_body["pathway_activations"], "expected pathway activations"
    assert report_body["biological_systems"], "expected biological systems"
    recs = report_body["recommendations"]
    assert len(recs) >= min_recommendations, recs