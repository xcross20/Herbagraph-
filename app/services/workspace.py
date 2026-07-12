"""Dashboard and patient overview aggregation."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis_session import AnalysisSession
from app.models.enums import LabResultStatus, PatientContextType
from app.models.lab import LabReport, LabResult
from app.models.patient import Patient
from app.models.patient_context import PatientContext
from app.models.report import RecommendationReport
from app.models.user import User
from app.schemas.workspace import (
    DashboardLabSummary,
    DashboardPatientSummary,
    DashboardReportSummary,
    DashboardSessionSummary,
    PatientOverviewRead,
    WorkspaceDashboardRead,
)
from app.services.patient_memory import ensure_default_patient

_ABNORMAL = {
    LabResultStatus.LOW,
    LabResultStatus.HIGH,
    LabResultStatus.CRITICAL_LOW,
    LabResultStatus.CRITICAL_HIGH,
}


def _report_dashboard_title(executive_summary: str | dict | None) -> str:
    """Short label for dashboard cards — executive_summary is stored as plain text."""
    if not executive_summary:
        return "Analysis Report"
    if isinstance(executive_summary, dict):
        headline = executive_summary.get("headline") or executive_summary.get("clinical_executive_summary")
        if headline:
            return str(headline)[:160]
        return "Analysis Report"
    text = str(executive_summary).strip()
    if not text:
        return "Analysis Report"
    first_line = text.splitlines()[0].strip()
    if len(first_line) > 160:
        return first_line[:157] + "..."
    return first_line


async def build_workspace_dashboard(db: AsyncSession, user: User) -> WorkspaceDashboardRead:
    patients_result = await db.execute(
        select(Patient).where(Patient.user_id == user.id).order_by(Patient.created_at.asc())
    )
    patients = list(patients_result.scalars().all())
    if not patients:
        from app import database

        sync = database.get_sync_db()
        try:
            ensure_default_patient(sync, user.id)
        finally:
            sync.close()
        patients_result = await db.execute(
            select(Patient).where(Patient.user_id == user.id).order_by(Patient.created_at.asc())
        )
        patients = list(patients_result.scalars().all())

    patient_summaries: list[DashboardPatientSummary] = []
    for patient in patients:
        lab_count = await db.scalar(
            select(func.count()).select_from(LabReport).where(LabReport.patient_id == patient.id)
        )
        session_count = await db.scalar(
            select(func.count()).select_from(AnalysisSession).where(AnalysisSession.patient_id == patient.id)
        )
        latest_report = await db.execute(
            select(RecommendationReport, LabReport.patient_id)
            .join(LabReport, RecommendationReport.lab_report_id == LabReport.id)
            .where(LabReport.patient_id == patient.id)
            .order_by(RecommendationReport.created_at.desc())
            .limit(1)
        )
        row = latest_report.first()
        patient_summaries.append(
            DashboardPatientSummary(
                id=patient.id,
                display_name=patient.display_name,
                latest_report_id=row[0].id if row else None,
                latest_report_confidence=row[0].overall_confidence if row else None,
                lab_report_count=lab_count or 0,
                analysis_session_count=session_count or 0,
            )
        )

    reports_result = await db.execute(
        select(RecommendationReport, LabReport.patient_id, Patient.display_name)
        .join(LabReport, RecommendationReport.lab_report_id == LabReport.id)
        .outerjoin(Patient, LabReport.patient_id == Patient.id)
        .where(RecommendationReport.user_id == user.id)
        .order_by(RecommendationReport.created_at.desc())
        .limit(8)
    )
    recent_reports = [
        DashboardReportSummary(
            id=report.id,
            patient_id=patient_id,
            patient_display_name=display_name,
            title=_report_dashboard_title(report.executive_summary),
            overall_confidence=report.overall_confidence,
            created_at=report.created_at,
            analysis_session_id=report.analysis_session_id,
        )
        for report, patient_id, display_name in reports_result.all()
    ]

    labs_result = await db.execute(
        select(LabReport)
        .where(LabReport.user_id == user.id)
        .order_by(LabReport.created_at.desc())
        .limit(8)
    )
    recent_labs = [
        DashboardLabSummary(
            id=lab.id,
            patient_id=lab.patient_id,
            original_filename=lab.original_filename,
            status=lab.status,
            latest_report_id=lab.latest_report_id,
            created_at=lab.created_at,
        )
        for lab in labs_result.scalars().all()
    ]

    sessions_result = await db.execute(
        select(AnalysisSession)
        .where(AnalysisSession.user_id == user.id)
        .order_by(AnalysisSession.created_at.desc())
        .limit(8)
    )
    recent_sessions = [
        DashboardSessionSummary(
            id=session.id,
            patient_id=session.patient_id,
            title=session.title,
            status=session.status,
            analysis_type=session.analysis_type,
            latest_report_id=session.latest_report_id,
            report_confidence=session.report_confidence,
            created_at=session.created_at,
        )
        for session in sessions_result.scalars().all()
    ]

    return WorkspaceDashboardRead(
        user_email=user.email,
        user_full_name=user.full_name,
        patients=patient_summaries,
        recent_reports=recent_reports,
        recent_labs=recent_labs,
        recent_sessions=recent_sessions,
    )


async def build_patient_overview(db: AsyncSession, user: User, patient_id: uuid.UUID) -> PatientOverviewRead:
    result = await db.execute(
        select(Patient).where(Patient.id == patient_id, Patient.user_id == user.id)
    )
    patient = result.scalar_one_or_none()
    if patient is None:
        raise ValueError("Patient not found")

    latest_report_row = await db.execute(
        select(RecommendationReport)
        .join(LabReport, RecommendationReport.lab_report_id == LabReport.id)
        .where(LabReport.patient_id == patient.id)
        .order_by(RecommendationReport.created_at.desc())
        .limit(1)
    )
    latest_report = latest_report_row.scalar_one_or_none()

    top_priorities: list[str] = []
    if latest_report and latest_report.report_insights:
        for item in (latest_report.report_insights.get("clinical_priorities") or [])[:3]:
            title = item.get("title") or item.get("biological_theme")
            if title:
                top_priorities.append(str(title))

    abnormal_rows = await db.execute(
        select(LabResult, LabReport.original_filename)
        .join(LabReport, LabResult.lab_report_id == LabReport.id)
        .where(LabReport.patient_id == patient.id, LabResult.status.in_(_ABNORMAL))
        .order_by(LabResult.created_at.desc())
        .limit(12)
    )
    recent_abnormal = [
        {
            "biomarker_name": row.biomarker_name,
            "value": row.value,
            "unit": row.unit,
            "status": row.status.value,
            "source_report": filename,
        }
        for row, filename in abnormal_rows.all()
    ]

    labs_result = await db.execute(
        select(LabReport).where(LabReport.patient_id == patient.id).order_by(LabReport.created_at.desc())
    )
    lab_reports = [
        DashboardLabSummary(
            id=lab.id,
            patient_id=lab.patient_id,
            original_filename=lab.original_filename,
            status=lab.status,
            latest_report_id=lab.latest_report_id,
            created_at=lab.created_at,
        )
        for lab in labs_result.scalars().all()
    ]

    sessions_result = await db.execute(
        select(AnalysisSession)
        .where(AnalysisSession.patient_id == patient.id)
        .order_by(AnalysisSession.created_at.desc())
    )
    analysis_sessions = [
        DashboardSessionSummary(
            id=session.id,
            patient_id=session.patient_id,
            title=session.title,
            status=session.status,
            analysis_type=session.analysis_type,
            latest_report_id=session.latest_report_id,
            report_confidence=session.report_confidence,
            created_at=session.created_at,
        )
        for session in sessions_result.scalars().all()
    ]

    context_result = await db.execute(
        select(PatientContext)
        .where(PatientContext.patient_id == patient.id, PatientContext.active.is_(True))
        .order_by(PatientContext.context_type, PatientContext.name)
    )
    context_summary: dict[str, list[str]] = {}
    for item in context_result.scalars().all():
        key = item.context_type.value
        context_summary.setdefault(key, []).append(item.name)

    dob = patient.date_of_birth.isoformat() if patient.date_of_birth else None
    return PatientOverviewRead(
        id=patient.id,
        display_name=patient.display_name,
        date_of_birth=dob,
        age=patient.age,
        biological_sex=patient.biological_sex,
        notes=patient.notes,
        created_at=patient.created_at,
        latest_report_id=latest_report.id if latest_report else None,
        latest_report_confidence=latest_report.overall_confidence if latest_report else None,
        top_priorities=top_priorities,
        recent_abnormal_biomarkers=recent_abnormal,
        lab_reports=lab_reports,
        analysis_sessions=analysis_sessions,
        context_summary=context_summary,
    )