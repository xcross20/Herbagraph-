"""Structured patient memory for context-aware report generation."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.analysis_session import AnalysisSession
from app.models.enums import LabReportStatus, LabResultStatus, PatientContextType
from app.models.lab import LabReport
from app.models.patient import Patient
from app.models.patient_context import PatientContext
from app.models.report import RecommendationReport
from app.models.user import HealthProfile

_ABNORMAL_STATUSES = {
    LabResultStatus.LOW,
    LabResultStatus.HIGH,
    LabResultStatus.CRITICAL_LOW,
    LabResultStatus.CRITICAL_HIGH,
}


def _prior_findings_from_reports(reports: list[RecommendationReport]) -> list[str]:
    findings: list[str] = []
    for report in reports:
        insights = report.report_insights or {}
        hero = insights.get("clinical_summary_hero") or {}
        primary = hero.get("primary_finding")
        if primary:
            findings.append(str(primary))
        for priority in (insights.get("clinical_priorities") or [])[:3]:
            title = priority.get("title") or priority.get("biological_theme")
            if title:
                findings.append(str(title))
    return findings[:8]


def _prior_missing_biomarkers(reports: list[RecommendationReport]) -> list[str]:
    missing: list[str] = []
    for report in reports:
        insights = report.report_insights or {}
        diagnostic = insights.get("diagnostic_optimization") or {}
        for step in diagnostic.get("diagnostic_next_steps") or []:
            name = step.get("biomarker") or step.get("test_name")
            if name:
                missing.append(str(name))
    return list(dict.fromkeys(missing))[:10]


def build_patient_memory(session: Session, patient_id: uuid.UUID | None, user_id: uuid.UUID) -> dict:
    """Aggregate structured memory for reasoning — no LLM memory yet."""
    profile = session.execute(select(HealthProfile).where(HealthProfile.user_id == user_id)).scalar_one_or_none()
    health = {
        "age_range": profile.age_range if profile else None,
        "biological_sex": profile.biological_sex if profile else None,
        "health_goals": list(profile.health_goals or []) if profile else [],
    }

    context_items: list[PatientContext] = []
    if patient_id is not None:
        context_items = list(
            session.execute(
                select(PatientContext)
                .where(PatientContext.patient_id == patient_id, PatientContext.active.is_(True))
                .order_by(PatientContext.created_at.desc())
            )
            .scalars()
            .all()
        )

    def _names(ctx_type: PatientContextType) -> list[str]:
        return [item.name for item in context_items if item.context_type == ctx_type]

    medications = _names(PatientContextType.MEDICATION)
    supplements = _names(PatientContextType.SUPPLEMENT)
    conditions = _names(PatientContextType.CONDITION)
    if profile:
        medications = list(dict.fromkeys(medications + list(profile.current_medications or [])))
        supplements = list(dict.fromkeys(supplements + list(profile.current_supplements or [])))
        conditions = list(dict.fromkeys(conditions + list(profile.known_conditions or [])))

    prior_reports_query = select(RecommendationReport).where(RecommendationReport.user_id == user_id)
    if patient_id is not None:
        prior_reports_query = prior_reports_query.join(
            LabReport, RecommendationReport.lab_report_id == LabReport.id
        ).where(LabReport.patient_id == patient_id)
    prior_reports = list(
        session.execute(prior_reports_query.order_by(RecommendationReport.created_at.desc()).limit(5))
        .scalars()
        .all()
    )

    prior_abnormals: list[str] = []
    lab_query = select(LabReport).where(
        LabReport.user_id == user_id, LabReport.status == LabReportStatus.COMPLETE
    )
    if patient_id is not None:
        lab_query = lab_query.where(LabReport.patient_id == patient_id)
    recent_labs = list(session.execute(lab_query.order_by(LabReport.created_at.desc()).limit(3)).scalars().all())
    for lab in recent_labs:
        session.refresh(lab, attribute_names=["lab_results"])
        for result in lab.lab_results:
            if result.status in _ABNORMAL_STATUSES:
                prior_abnormals.append(f"{result.biomarker_name} {result.status.value}")

    session_count = 0
    if patient_id is not None:
        session_count = (
            session.execute(
                select(AnalysisSession).where(
                    AnalysisSession.patient_id == patient_id, AnalysisSession.user_id == user_id
                )
            )
            .scalars()
            .all()
        )
        session_count = len(session_count)

    diet_patterns = _names(PatientContextType.DIET_PATTERN)
    return {
        "patient_context": {
            "current_medications": medications,
            "current_supplements": supplements,
            "known_conditions": conditions,
            "diet_pattern": diet_patterns[0] if diet_patterns else None,
            "goals": _names(PatientContextType.GOAL),
            "prior_findings": _prior_findings_from_reports(prior_reports),
            "prior_missing_biomarkers": _prior_missing_biomarkers(prior_reports),
            "prior_abnormal_biomarkers": list(dict.fromkeys(prior_abnormals))[:12],
            "prior_analysis_count": session_count,
            **health,
        }
    }


def ensure_default_patient(session: Session, user_id: uuid.UUID) -> Patient:
    """Create a 'Self' patient profile when a user has none."""
    existing = session.execute(select(Patient).where(Patient.user_id == user_id).limit(1)).scalar_one_or_none()
    if existing is not None:
        return existing
    patient = Patient(user_id=user_id, display_name="Self")
    session.add(patient)
    session.commit()
    session.refresh(patient)
    return patient