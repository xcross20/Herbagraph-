"""Celery task definitions.

Runs Stage 1 (lab_parser) + Stage 2 (biomarker_normalizer) in the background
after a lab report is uploaded. Uses a plain synchronous DB session so the
task never needs an event loop of its own -- it is equally safe to invoke
via a real Celery worker process or eagerly in-process during tests.
"""

from sqlalchemy import select

from app import database
from app.core.file_storage import load_lab_file
from app.models.enums import AuditAction, LabProcessingStage, LabReportStatus
from app.services.audit import record_audit_event_sync
from app.models.lab import LabReport, LabResult
from app.models.user import HealthProfile
from app.pipeline.biomarker_normalizer import canonical_name_for_persist, normalize_lab_results
from app.pipeline.llm_alias_resolver import apply_alias_map_to_parsed, resolve_aliases_with_llm
from app.pipeline.user_biomarker_profile import (
    prune_custom_biomarkers_overlapping_catalog,
    register_discovered_biomarkers,
    resolve_canonical_name,
)
from app.pipeline.lab_parser import parse_lab_file_with_llm_fallback
from app.services.integrated_analysis import run_integrated_analysis
from app.services.report_generation import run_report_generation
from app.workers.celery_app import celery_app


def _apply_llm_alias_assist(parsed: list, custom_biomarkers: list | None) -> list:
    """IMP-053: after deterministic aliases fail, ask LLM (or mock heuristics)."""
    unresolved = [
        p.raw_test_name
        for p in parsed
        if p.raw_test_name and not resolve_canonical_name(p.raw_test_name, custom_biomarkers)
    ]
    if not unresolved:
        return parsed
    try:
        import asyncio

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            alias_map = asyncio.run(
                resolve_aliases_with_llm(unresolved, custom_biomarkers=custom_biomarkers)
            )
        else:
            # Nested loop (pytest-asyncio): run in a worker thread
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                alias_map = pool.submit(
                    asyncio.run,
                    resolve_aliases_with_llm(unresolved, custom_biomarkers=custom_biomarkers),
                ).result()
        return apply_alias_map_to_parsed(parsed, alias_map)
    except Exception:  # noqa: BLE001 — never fail parse pipeline on alias assist
        return parsed


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
            file_bytes = load_lab_file(lab_report.encrypted_file_path, lab_report.encrypted_file_data)
            parsed = parse_lab_file_with_llm_fallback(file_bytes, lab_report.original_filename)

            if not parsed and file_bytes.strip():
                raise ValueError(
                    "No biomarker rows could be extracted from this lab report. "
                    "Regex parsing and LLM-assisted extraction both returned empty. "
                    "Try a text/CSV export from your lab portal, or one of the demo samples in samples/lab_reports/."
                )

            _set_processing_stage(session, lab_report, LabProcessingStage.NORMALIZING)
            profile = session.execute(
                select(HealthProfile).where(HealthProfile.user_id == lab_report.user_id)
            ).scalar_one_or_none()
            custom_biomarkers = prune_custom_biomarkers_overlapping_catalog(
                list(profile.custom_biomarkers or []) if profile else []
            )
            if profile is not None and custom_biomarkers != list(profile.custom_biomarkers or []):
                profile.custom_biomarkers = custom_biomarkers
                session.add(profile)

            parsed = _apply_llm_alias_assist(parsed, custom_biomarkers)
            normalized = normalize_lab_results(parsed, custom_biomarkers=custom_biomarkers)

            if profile is not None:
                updated_profile = register_discovered_biomarkers(normalized, custom_biomarkers)
                if updated_profile != custom_biomarkers:
                    profile.custom_biomarkers = updated_profile
                    session.add(profile)

            for result in normalized:
                session.add(
                    LabResult(
                        lab_report_id=lab_report.id,
                        biomarker_name=canonical_name_for_persist(result, custom_biomarkers),
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
            record_audit_event_sync(
                session,
                action=AuditAction.LAB_PARSED,
                summary=f"Parser extracted {len(normalized)} biomarkers from {lab_report.original_filename}",
                user_id=lab_report.user_id,
                patient_id=lab_report.patient_id,
                resource_type="lab_report",
                resource_id=str(lab_report.id),
                detail={"biomarker_count": len(normalized), "filename": lab_report.original_filename},
            )
            session.commit()
            return {"status": "complete", "lab_report_id": lab_report_id, "biomarker_count": len(normalized)}
        except Exception as exc:  # noqa: BLE001 - persist any processing failure onto the report
            session.rollback()
            lab_report.status = LabReportStatus.FAILED
            lab_report.processing_stage = LabProcessingStage.FAILED
            lab_report.error_message = str(exc)
            record_audit_event_sync(
                session,
                action=AuditAction.LAB_PARSE_FAILED,
                summary=f"Lab parse failed for {lab_report.original_filename}",
                user_id=lab_report.user_id,
                patient_id=lab_report.patient_id,
                resource_type="lab_report",
                resource_id=str(lab_report.id),
                detail={"error": str(exc)},
            )
            session.commit()
            return {"status": "failed", "error": str(exc)}
    finally:
        session.close()


@celery_app.task(name="process_lab_report")
def process_lab_report_task(lab_report_id: str) -> dict:
    return process_lab_report(lab_report_id)


def generate_recommendation_report(
    lab_report_id: str, user_id: str, knowledge_path: str = "legacy"
) -> dict:
    return run_report_generation(lab_report_id, user_id, knowledge_path=knowledge_path)


@celery_app.task(name="generate_recommendation_report")
def generate_recommendation_report_task(
    lab_report_id: str, user_id: str, knowledge_path: str = "legacy"
) -> dict:
    return generate_recommendation_report(lab_report_id, user_id, knowledge_path=knowledge_path)


@celery_app.task(name="run_integrated_analysis")
def run_integrated_analysis_task(
    analysis_session_id: str, user_id: str, knowledge_path: str = "legacy"
) -> dict:
    return run_integrated_analysis(analysis_session_id, user_id, knowledge_path=knowledge_path)