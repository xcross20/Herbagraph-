"""Integrated lab analysis: wait for parses, merge biomarkers, run pipeline once."""

from __future__ import annotations

import asyncio
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import delete, select

from app import database
from app.models.analysis_session import AnalysisSession, AnalysisSessionLabReport, IntegratedBiomarkerResult
from app.models.enums import AnalysisSessionStatus, AuditAction, LabReportStatus, ReportGenerationStage
from app.services.audit import record_audit_event_sync
from app.models.lab import LabReport
from app.models.user import HealthProfile
from app.models.enums import LabResultStatus
from app.pipeline.biomarker_normalizer import classify_lab_value, get_reference_data
from app.pipeline.integrated_merge import merge_lab_reports
from app.pipeline.trend_context import build_trend_context
from app.schemas.pipeline import NormalizedLabResult
from app.models.enums import AnalysisType
from app.services.patient_memory import build_patient_memory
from app.services.report_generation import _health_profile_dict, _run_pipeline_stages

_PARSE_POLL_SECONDS = 2
_PARSE_TIMEOUT_SECONDS = 15 * 60


def _set_session_status(session, analysis_session: AnalysisSession, status: AnalysisSessionStatus) -> None:
    analysis_session.status = status
    session.commit()


def _fetch_lab_reports_fresh(lab_report_ids: list[uuid.UUID]) -> list[LabReport]:
    """Read lab report status in a throwaway session (avoids SQLAlchemy identity-map staleness)."""
    poll = database.get_sync_db()
    try:
        return list(
            poll.execute(select(LabReport).where(LabReport.id.in_(lab_report_ids))).scalars().all()
        )
    finally:
        poll.close()


def _wait_for_lab_parses(session, lab_report_ids: list[uuid.UUID]) -> list[LabReport]:
    deadline = time.monotonic() + _PARSE_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        reports = _fetch_lab_reports_fresh(lab_report_ids)
        if len(reports) != len(lab_report_ids):
            raise ValueError("One or more lab reports were deleted before parsing finished.")

        statuses = {r.status for r in reports}
        if LabReportStatus.FAILED in statuses:
            failed = [r for r in reports if r.status == LabReportStatus.FAILED]
            messages = "; ".join(
                f"{r.original_filename}: {r.error_message or 'parse failed'}" for r in failed
            )
            raise ValueError(f"Lab parsing failed: {messages}")

        if all(r.status == LabReportStatus.COMPLETE for r in reports):
            session.expire_all()
            refreshed = list(
                session.execute(select(LabReport).where(LabReport.id.in_(lab_report_ids))).scalars().all()
            )
            for report in refreshed:
                session.refresh(report, attribute_names=["lab_results"])
            return refreshed

        time.sleep(_PARSE_POLL_SECONDS)

    raise TimeoutError("Timed out waiting for all lab reports to finish parsing.")


def _persist_integrated_results(session, analysis_session_id: uuid.UUID, merge_result) -> None:
    session.execute(
        delete(IntegratedBiomarkerResult).where(
            IntegratedBiomarkerResult.analysis_session_id == analysis_session_id
        )
    )
    for row in merge_result.integrated_rows:
        session.add(
            IntegratedBiomarkerResult(
                analysis_session_id=analysis_session_id,
                biomarker_name=row["biomarker_name"],
                value=row["value"],
                unit=row["unit"],
                source_lab_report_id=uuid.UUID(row["source_lab_report_id"]),
                collected_at=row["collected_at"],
                confidence=row["confidence"],
                merge_note=row.get("merge_note"),
                is_snapshot=row["is_snapshot"],
            )
        )
    session.commit()


def _integrated_analysis_metadata(merge_result) -> dict:
    source_count = len(merge_result.sources)
    return {
        "source_count": source_count,
        "banner": f"Integrated from {source_count} lab report{'s' if source_count != 1 else ''}",
        "sources": merge_result.sources,
        "conflicts": merge_result.conflicts,
    }


def _prior_labs_from_merge(merge_result) -> list[NormalizedLabResult]:
    by_name: dict[str, list[dict]] = defaultdict(list)
    for row in merge_result.integrated_rows:
        if not row["is_snapshot"]:
            by_name[row["biomarker_name"]].append(row)

    prior: list[NormalizedLabResult] = []
    for biomarker_name, rows in by_name.items():
        rows.sort(
            key=lambda r: r["collected_at"] or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        top = rows[0]
        ref = get_reference_data(biomarker_name)
        if ref:
            status = classify_lab_value(
                top["value"],
                ref.get("reference_low"),
                ref.get("reference_high"),
                ref.get("optimal_low"),
                ref.get("optimal_high"),
                ref.get("critical_low"),
                ref.get("critical_high"),
            )
        else:
            status = LabResultStatus.NORMAL
        prior.append(
            NormalizedLabResult(
                biomarker_name=biomarker_name,
                raw_test_name=biomarker_name,
                value=top["value"],
                unit=top["unit"],
                status=status,
            )
        )
    return prior


def _anchor_lab_report(lab_reports: list[LabReport]) -> LabReport:
    return max(
        lab_reports,
        key=lambda r: r.created_at or datetime.min.replace(tzinfo=timezone.utc),
    )


async def _run_integrated_analysis_async(
    analysis_session_id: str, user_id: str, knowledge_path: str = "legacy"
) -> dict:
    session = database.get_sync_db()
    try:
        analysis_session = session.get(AnalysisSession, analysis_session_id)
        if analysis_session is None:
            return {"status": "failed", "error": "analysis_session_not_found"}
        if str(analysis_session.user_id) != user_id:
            return {"status": "failed", "error": "forbidden"}

        links = session.execute(
            select(AnalysisSessionLabReport).where(
                AnalysisSessionLabReport.analysis_session_id == analysis_session.id
            )
        ).scalars().all()
        if len(links) < 1:
            return {"status": "failed", "error": "integrated_analysis_requires_at_least_one_lab_report"}

        lab_report_ids = [link.lab_report_id for link in links]
        panel_labels = {str(link.lab_report_id): link.panel_label for link in links if link.panel_label}

        analysis_session.error_message = None
        _set_session_status(session, analysis_session, AnalysisSessionStatus.PARSING)

        # Always re-parse from stored originals so parser upgrades (MyChart Result Trends
        # latest-date, unit scaling) apply without requiring the user to re-upload.
        from app.workers.tasks import process_lab_report

        for lid in lab_report_ids:
            try:
                result = process_lab_report(str(lid), force=True)
                if result.get("status") == "failed":
                    analysis_session.error_message = (
                        f"Lab re-parse failed: {result.get('error') or 'unknown error'}"
                    )
                    _set_session_status(session, analysis_session, AnalysisSessionStatus.FAILED)
                    return {"status": "failed", "error": analysis_session.error_message}
            except Exception as exc:  # noqa: BLE001
                analysis_session.error_message = f"Lab re-parse failed: {exc}"
                _set_session_status(session, analysis_session, AnalysisSessionStatus.FAILED)
                return {"status": "failed", "error": analysis_session.error_message}

        try:
            lab_reports = _wait_for_lab_parses(session, lab_report_ids)
        except (TimeoutError, ValueError) as exc:
            analysis_session.error_message = str(exc)
            _set_session_status(session, analysis_session, AnalysisSessionStatus.FAILED)
            return {"status": "failed", "error": str(exc)}

        if not all(report.lab_results for report in lab_reports):
            empty = [r.original_filename for r in lab_reports if not r.lab_results]
            analysis_session.error_message = (
                "One or more lab reports have no parsed biomarkers: "
                + ", ".join(empty)
                + ". Re-upload the PDF or confirm the file is a MyChart Result Trends / lab export."
            )
            _set_session_status(session, analysis_session, AnalysisSessionStatus.FAILED)
            return {"status": "failed", "error": analysis_session.error_message}

        _set_session_status(session, analysis_session, AnalysisSessionStatus.MERGING)

        profile = session.execute(
            select(HealthProfile).where(HealthProfile.user_id == analysis_session.user_id)
        ).scalar_one_or_none()
        custom_biomarkers = list(profile.custom_biomarkers or []) if profile else []

        merge_result = merge_lab_reports(
            lab_reports,
            panel_labels=panel_labels,
            custom_biomarkers=custom_biomarkers,
        )
        if not merge_result.snapshot:
            analysis_session.error_message = "No biomarkers could be merged from the uploaded lab reports."
            _set_session_status(session, analysis_session, AnalysisSessionStatus.FAILED)
            return {"status": "failed", "error": analysis_session.error_message}

        _persist_integrated_results(session, analysis_session.id, merge_result)
        integrated_meta = _integrated_analysis_metadata(merge_result)

        anchor = _anchor_lab_report(lab_reports)
        anchor.report_stage = ReportGenerationStage.QUEUED
        anchor.report_error_message = None
        session.commit()

        _set_session_status(session, analysis_session, AnalysisSessionStatus.ANALYZING)

        prior_labs = _prior_labs_from_merge(merge_result)
        prior_dates = [
            row["collected_at"].isoformat()
            for row in merge_result.integrated_rows
            if not row["is_snapshot"] and row["collected_at"]
        ]
        prior_date = max(prior_dates) if prior_dates else None
        lab_trends = build_trend_context(
            merge_result.snapshot,
            prior_labs if prior_labs else None,
            prior_report_date=prior_date,
        )
        if prior_labs:
            lab_trends = {
                **lab_trends,
                "summary": (
                    f"Compared integrated snapshot to {len(prior_labs)} biomarker(s) from prior uploads in this session. "
                    + lab_trends.get("summary", "")
                ),
            }

        health_profile = _health_profile_dict(profile)
        patient_id = analysis_session.patient_id or anchor.patient_id
        if analysis_session.analysis_type == AnalysisType.LONGITUDINAL_COMPARISON and patient_id:
            memory = build_patient_memory(session, patient_id, analysis_session.user_id)
            prior_findings = memory.get("patient_context", {}).get("prior_findings") or []
            if prior_findings:
                lab_trends = {
                    **lab_trends,
                    "longitudinal_note": (
                        "Compared to prior analyses for this patient. "
                        + "; ".join(prior_findings[:3])
                    ),
                }

        report = await _run_pipeline_stages(
            anchor,
            health_profile,
            session,
            normalized_labs=merge_result.snapshot,
            integrated_analysis=integrated_meta,
            analysis_session_id=analysis_session.id,
            lab_trends_override=lab_trends,
            patient_id=patient_id,
            knowledge_path=knowledge_path,
        )

        analysis_session.latest_report_id = report.id
        analysis_session.report_confidence = report.overall_confidence
        analysis_session.analysis_date = datetime.now(timezone.utc)
        record_audit_event_sync(
            session,
            action=AuditAction.ANALYSIS_COMPLETED,
            summary=f"Integrated analysis completed ({analysis_session.title})",
            user_id=analysis_session.user_id,
            patient_id=patient_id,
            resource_type="analysis_session",
            resource_id=str(analysis_session.id),
            detail={
                "report_id": str(report.id),
                "lab_count": len(lab_report_ids),
                "confidence": report.overall_confidence,
            },
        )
        _set_session_status(session, analysis_session, AnalysisSessionStatus.COMPLETE)
        return {
            "status": "complete",
            "analysis_session_id": str(analysis_session.id),
            "report_id": str(report.id),
        }
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        analysis_session = session.get(AnalysisSession, analysis_session_id)
        if analysis_session is not None:
            analysis_session.status = AnalysisSessionStatus.FAILED
            analysis_session.error_message = str(exc)
            session.commit()
        return {"status": "failed", "error": str(exc)}
    finally:
        session.close()


def run_integrated_analysis(
    analysis_session_id: str, user_id: str, knowledge_path: str = "legacy"
) -> dict:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(
            _run_integrated_analysis_async(analysis_session_id, user_id, knowledge_path)
        )

    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(
            asyncio.run,
            _run_integrated_analysis_async(analysis_session_id, user_id, knowledge_path),
        ).result()