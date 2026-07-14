"""Worker-path integration: process_lab_report through real parse + normalize + persist.

Catches blindspots that unit tests miss when only calling parse_lab_text() directly:
- canonical_name_for_persist after normalize
- full file read/decrypt path
- exception handling persisted to lab_report.error_message
"""

import uuid
from pathlib import Path

import pytest

from app import database
from app.core.file_storage import save_lab_file
from app.models.enums import LabProcessingStage, LabReportStatus
from app.models.lab import LabReport, LabResult
from app.pipeline.user_biomarker_profile import is_catalog_biomarker
from app.workers.tasks import process_lab_report

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]

_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.mark.parametrize(
    "fixture_name,expected_names,min_count",
    [
        ("healow_lipid_panel_excerpt.txt", {"HDL", "LDL", "Total Cholesterol"}, 6),
        (
            None,
            {"HDL", "LDL"},
            2,
        ),
    ],
    ids=["healow_excerpt", "f_prefix_inline"],
)
async def test_process_lab_report_blindspot_fixtures(
    db_session,
    test_user,
    fixture_name,
    expected_names,
    min_count,
):
    if fixture_name:
        raw = (_FIXTURES / fixture_name).read_bytes()
        filename = fixture_name
    else:
        raw = (
            b"F HDL 48.0 L 60.00 - 180.00 (mg/dL)\n"
            b"F LDL Cholesterol Calc 142.00 H 0.00 - 99.00\n"
        )
        filename = "f_prefix_lipids.txt"

    saved = save_lab_file(raw, uuid.uuid4(), filename)
    lab_report = LabReport(
        user_id=test_user.id,
        original_filename=filename,
        encrypted_file_path=saved.encrypted_file_path,
        file_size_bytes=len(raw),
        status=LabReportStatus.PENDING,
    )
    db_session.add(lab_report)
    await db_session.commit()
    await db_session.refresh(lab_report)

    result = process_lab_report(str(lab_report.id))

    assert result["status"] == "complete", result.get("error")
    assert result["biomarker_count"] >= min_count

    sync_session = database.get_sync_db()
    try:
        persisted = sync_session.get(LabReport, str(lab_report.id))
        assert persisted.status == LabReportStatus.COMPLETE
        assert persisted.processing_stage == LabProcessingStage.COMPLETE
        assert not persisted.error_message

        rows = sync_session.query(LabResult).filter_by(lab_report_id=lab_report.id).all()
        names = {r.biomarker_name for r in rows}
        assert expected_names.issubset(names), names
        assert all(is_catalog_biomarker(r.biomarker_name) for r in rows), [
            r.biomarker_name for r in rows if not is_catalog_biomarker(r.biomarker_name)
        ]
    finally:
        sync_session.close()


async def test_process_lab_report_healow_does_not_crash_on_ocr_variant_lists(db_session, test_user):
    """Regression: nested OCR variant lists caused 'list' object has no attribute 'strip'."""
    raw = (_FIXTURES / "healow_lipid_panel_excerpt.txt").read_bytes()
    # Use .txt — excerpt is plain text; .pdf would invoke the PDF extractor and fail.
    saved = save_lab_file(raw, uuid.uuid4(), "healow_lipids.txt")
    lab_report = LabReport(
        user_id=test_user.id,
        original_filename="healow_lipids.txt",
        encrypted_file_path=saved.encrypted_file_path,
        file_size_bytes=len(raw),
        status=LabReportStatus.PENDING,
    )
    db_session.add(lab_report)
    await db_session.commit()
    await db_session.refresh(lab_report)

    result = process_lab_report(str(lab_report.id))

    assert result["status"] == "complete", result.get("error")
    assert "strip" not in (result.get("error") or "")