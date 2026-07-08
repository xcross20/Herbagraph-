"""Every CI lab scenario must survive the real worker path (parse → normalize → persist)."""

from __future__ import annotations

import uuid

import pytest

from app import database
from app.core.file_storage import save_lab_file
from app.models.enums import LabProcessingStage, LabReportStatus
from app.models.lab import LabReport, LabResult
from app.pipeline.lab_scenario_loader import list_scenarios, resolve_raw_path
from app.pipeline.user_biomarker_profile import is_catalog_biomarker
from app.workers.tasks import process_lab_report

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]

SCENARIOS_ROOT = resolve_raw_path(list_scenarios()[0]).parent.parent


def _ci_scenarios() -> list[dict]:
    return [s for s in list_scenarios() if not s.get("skip_ci")]


@pytest.mark.parametrize("scenario", _ci_scenarios(), ids=lambda s: s["scenario_id"])
async def test_process_lab_report_survives_scenario(db_session, test_user, scenario: dict):
    """Worker must complete (or fail gracefully) — never raise uncaught exceptions."""
    path = resolve_raw_path(scenario, SCENARIOS_ROOT)
    raw = path.read_bytes()

    encrypted_path = save_lab_file(raw, uuid.uuid4(), path.name)
    lab_report = LabReport(
        user_id=test_user.id,
        original_filename=path.name,
        encrypted_file_path=encrypted_path,
        file_size_bytes=len(raw),
        status=LabReportStatus.PENDING,
    )
    db_session.add(lab_report)
    await db_session.commit()
    await db_session.refresh(lab_report)

    result = process_lab_report(str(lab_report.id))

    assert result["status"] == "complete", (
        f"{scenario['scenario_id']}: worker failed — {result.get('error')}"
    )

    min_rows = scenario.get("expect", {}).get("parse", {}).get("min_rows", 1)
    assert result["biomarker_count"] >= min_rows, (
        f"{scenario['scenario_id']}: expected >= {min_rows} rows, got {result['biomarker_count']}"
    )

    sync_session = database.get_sync_db()
    try:
        persisted = sync_session.get(LabReport, str(lab_report.id))
        assert persisted.status == LabReportStatus.COMPLETE
        assert persisted.processing_stage == LabProcessingStage.COMPLETE
        assert not persisted.error_message

        rows = sync_session.query(LabResult).filter_by(lab_report_id=lab_report.id).all()
        custom = scenario.get("custom_biomarkers")
        # Kitchen-sink / real exports may persist urinalysis and niche rows outside the catalog.
        allow_extras = "kitchen_sink" in scenario.get("tags", [])
        if not custom and not allow_extras:
            bad = [r.biomarker_name for r in rows if not is_catalog_biomarker(r.biomarker_name)]
            assert not bad, f"{scenario['scenario_id']}: non-catalog persisted names: {bad}"

        for spec in scenario.get("expect", {}).get("normalize", {}).get("must_include", []):
            name = spec["biomarker_name"]
            match = next((r for r in rows if r.biomarker_name == name), None)
            assert match is not None, f"{scenario['scenario_id']}: missing persisted {name!r}"
    finally:
        sync_session.close()