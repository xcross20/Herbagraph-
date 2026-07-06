import uuid

import pytest

from app import database
from app.core.file_storage import save_lab_file
from app.models.enums import LabProcessingStage, LabReportStatus
from app.models.lab import LabReport
from app.workers.tasks import process_lab_report, process_lab_report_task

pytestmark = pytest.mark.asyncio

VALID_LAB_TEXT = (
    b"CRP                    8.20  mg/L   (0.00-3.00)\n"
    b"Glucose                95.00  mg/dL   (70.00-99.00)\n"
)


async def test_process_lab_report_happy_path_parses_and_persists(db_session, test_user):
    encrypted_path = save_lab_file(VALID_LAB_TEXT, uuid.uuid4(), "labs.txt")
    lab_report = LabReport(
        user_id=test_user.id,
        original_filename="labs.txt",
        encrypted_file_path=encrypted_path,
        file_size_bytes=len(VALID_LAB_TEXT),
        status=LabReportStatus.PENDING,
    )
    db_session.add(lab_report)
    await db_session.commit()
    await db_session.refresh(lab_report)

    result = process_lab_report(str(lab_report.id))

    assert result["status"] == "complete"
    assert result["lab_report_id"] == str(lab_report.id)
    assert result["biomarker_count"] == 2

    sync_session = database.get_sync_db()
    try:
        persisted = sync_session.get(LabReport, str(lab_report.id))
        assert persisted.status == LabReportStatus.COMPLETE
        assert persisted.processing_stage == LabProcessingStage.COMPLETE
        from app.models.lab import LabResult

        results = sync_session.query(LabResult).filter_by(lab_report_id=lab_report.id).all()
        assert len(results) == 2
        names = {r.biomarker_name for r in results}
        assert "CRP" in names
    finally:
        sync_session.close()


async def test_process_lab_report_nonexistent_id_returns_failed(db_session):
    result = process_lab_report(str(uuid.uuid4()))
    assert result == {"status": "failed", "error": "lab_report_not_found"}


async def test_process_lab_report_task_wrapper_delegates(db_session, test_user):
    encrypted_path = save_lab_file(VALID_LAB_TEXT, uuid.uuid4(), "labs.txt")
    lab_report = LabReport(
        user_id=test_user.id,
        original_filename="labs.txt",
        encrypted_file_path=encrypted_path,
        file_size_bytes=len(VALID_LAB_TEXT),
        status=LabReportStatus.PENDING,
    )
    db_session.add(lab_report)
    await db_session.commit()
    await db_session.refresh(lab_report)

    result = process_lab_report_task(str(lab_report.id))
    assert result["status"] == "complete"
    assert result["biomarker_count"] == 2


async def test_process_lab_report_persists_reference_ranges_and_units(db_session, test_user):
    encrypted_path = save_lab_file(VALID_LAB_TEXT, uuid.uuid4(), "labs.txt")
    lab_report = LabReport(
        user_id=test_user.id,
        original_filename="labs.txt",
        encrypted_file_path=encrypted_path,
        file_size_bytes=len(VALID_LAB_TEXT),
        status=LabReportStatus.PENDING,
    )
    db_session.add(lab_report)
    await db_session.commit()
    await db_session.refresh(lab_report)

    process_lab_report(str(lab_report.id))

    sync_session = database.get_sync_db()
    try:
        from app.models.lab import LabResult

        crp = (
            sync_session.query(LabResult)
            .filter_by(lab_report_id=lab_report.id, biomarker_name="CRP")
            .one()
        )
        assert crp.unit == "mg/L"
        assert crp.reference_range_low == 0.0
        assert crp.reference_range_high == 3.0
        assert crp.value == 8.2
    finally:
        sync_session.close()


async def test_process_lab_report_no_parseable_lines_completes_with_zero_biomarkers(db_session, test_user):
    encrypted_path = save_lab_file(b"this file has no parseable lab lines at all\n", uuid.uuid4(), "labs.txt")
    lab_report = LabReport(
        user_id=test_user.id,
        original_filename="labs.txt",
        encrypted_file_path=encrypted_path,
        file_size_bytes=10,
        status=LabReportStatus.PENDING,
    )
    db_session.add(lab_report)
    await db_session.commit()
    await db_session.refresh(lab_report)

    result = process_lab_report(str(lab_report.id))
    assert result == {
        "status": "complete",
        "lab_report_id": str(lab_report.id),
        "biomarker_count": 0,
    }


async def test_process_lab_report_bad_file_sets_status_failed(db_session, test_user):
    # An encrypted_file_path that isn't a valid Fernet token will blow up in load_lab_file's
    # decrypt_str call, which process_lab_report should catch and persist as a failure.
    lab_report = LabReport(
        user_id=test_user.id,
        original_filename="corrupt.txt",
        encrypted_file_path="not-a-valid-fernet-token",
        file_size_bytes=10,
        status=LabReportStatus.PENDING,
    )
    db_session.add(lab_report)
    await db_session.commit()
    await db_session.refresh(lab_report)

    result = process_lab_report(str(lab_report.id))

    assert result["status"] == "failed"
    assert "error" in result

    sync_session = database.get_sync_db()
    try:
        persisted = sync_session.get(LabReport, str(lab_report.id))
        assert persisted.status == LabReportStatus.FAILED
        assert persisted.error_message
    finally:
        sync_session.close()


async def test_process_lab_report_missing_file_on_disk_sets_status_failed(db_session, test_user):
    from app.core.privacy import encrypt_str

    # A validly-encrypted path token pointing at a file that doesn't exist on disk.
    bogus_path_token = encrypt_str("/nonexistent/path/does-not-exist.txt.enc")
    lab_report = LabReport(
        user_id=test_user.id,
        original_filename="missing.txt",
        encrypted_file_path=bogus_path_token,
        file_size_bytes=10,
        status=LabReportStatus.PENDING,
    )
    db_session.add(lab_report)
    await db_session.commit()
    await db_session.refresh(lab_report)

    result = process_lab_report(str(lab_report.id))

    assert result["status"] == "failed"

    sync_session = database.get_sync_db()
    try:
        persisted = sync_session.get(LabReport, str(lab_report.id))
        assert persisted.status == LabReportStatus.FAILED
        assert persisted.error_message
    finally:
        sync_session.close()
