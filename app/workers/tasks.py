"""Celery task definitions.

Runs Stage 1 (lab_parser) + Stage 2 (biomarker_normalizer) in the background
after a lab report is uploaded. Uses a plain synchronous DB session so the
task never needs an event loop of its own -- it is equally safe to invoke
via a real Celery worker process or eagerly in-process during tests.
"""

from app import database
from app.core.file_storage import load_lab_file
from app.models.enums import LabProcessingStage, LabReportStatus, ReportGenerationStage
from app.models.lab import LabReport, LabResult
from app.pipeline.biomarker_normalizer import normalize_lab_results
from app.pipeline.lab_parser import parse_lab_file
from app.services.report_generation import run_report_generation
from app.workers.celery_app import celery_app


def _set_processing_stage(session, lab_report: LabReport, stage: LabProcessingStage) -> None:
    lab_report.processing_stage = stage
    session.commit()


def process_lab_report(lab_report_id: str) -> dict:
    """Stage 1 + Stage 2, synchronously: parse the uploaded file and persist normalized LabResults."""
    session = database.get_sync_db()
    try:
        lab_report = session.get(LabReport, lab_report_id)
        if lab_report is None:
            return {"status": "failed", "error": "lab_report_not_found"}

        lab_report.status = LabReportStatus.PROCESSING
        _set_processing_stage(session, lab_report, LabProcessingStage.QUEUED)

        try:
            _set_processing_stage(session, lab_report, LabProcessingStage.PARSING)
            file_bytes = load_lab_file(lab_report.encrypted_file_path)
            parsed = parse_lab_file(file_bytes, lab_report.original_filename)

            _set_processing_stage(session, lab_report, LabProcessingStage.NORMALIZING)
            normalized = normalize_lab_results(parsed)

            for result in normalized:
                session.add(
                    LabResult(
                        lab_report_id=lab_report.id,
                        biomarker_name=result.biomarker_name,
                        raw_test_name=result.raw_test_name,
                        value=result.value,
                        unit=result.unit,
                        reference_range_low=result.reference_range_low,
                        reference_range_high=result.reference_range_high,
                        status=result.status,
                    )
                )
            lab_report.status = LabReportStatus.COMPLETE
            lab_report.processing_stage = LabProcessingStage.COMPLETE
            session.commit()
            return {"status": "complete", "lab_report_id": lab_report_id, "biomarker_count": len(normalized)}
        except Exception as exc:  # noqa: BLE001 - persist any processing failure onto the report
            session.rollback()
            lab_report.status = LabReportStatus.FAILED
            lab_report.processing_stage = LabProcessingStage.FAILED
            lab_report.error_message = str(exc)
            session.commit()
            return {"status": "failed", "error": str(exc)}
    finally:
        session.close()


@celery_app.task(name="process_lab_report")
def process_lab_report_task(lab_report_id: str) -> dict:
    return process_lab_report(lab_report_id)


def generate_recommendation_report(lab_report_id: str, user_id: str) -> dict:
    return run_report_generation(lab_report_id, user_id)


@celery_app.task(name="generate_recommendation_report")
def generate_recommendation_report_task(lab_report_id: str, user_id: str) -> dict:
    return generate_recommendation_report(lab_report_id, user_id)