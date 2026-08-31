"""Dashboard and patient overview aggregation."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis_session import AnalysisSession
from app.models.enums import LabResultStatus
from app.models.lab import LabReport, LabResult
from app.models.patient import Patient
from app.models.patient_context import PatientContext
from app.models.report import RecommendationReport
from app.models.user import User
from app.schemas.workspace import (
    CaseOverview,
    CaseOverviewBranch,
    CaseOverviewConcern,
    CaseOverviewCoverageExplanation,
    CaseOverviewDataCompleteness,
    CaseOverviewFinding,
    CaseOverviewGap,
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
        feature_flags={
            "personal_evidence_regimen_v1": _is_pe_regimen_enabled(),
            "case_overview_v1": _is_case_overview_enabled(),
        },
    )


def _is_pe_regimen_enabled() -> bool:
    from app.config import get_settings

    settings = get_settings()
    env = (getattr(settings, "app_env", "") or "").lower()
    if env in {"uat", "preview"}:
        return True
    return bool(getattr(settings, "personal_evidence_regimen_v1", False))


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


def _is_case_overview_enabled() -> bool:
    from app.config import get_settings

    settings = get_settings()
    env = (getattr(settings, "app_env", "") or "").lower()
    if env in {"uat", "preview"}:
        return True
    return bool(getattr(settings, "case_overview_v1", False))


def _finding_provenance(source: str | None, kind: str, value: str | None) -> str:
    """Derive provenance label from a finding's source, kind, and value."""
    if source == "lab_engine":
        return "verified"
    val = (value or "").lower()
    if "unverified" in val or val in {"mentioned", "reported_normal", "reported_abnormal"}:
        return "reported"
    if kind == "assessment" and val == "already_assessed":
        return "reported"
    if source in {"intake", "user"}:
        return "reported"
    return "inferred"


async def build_case_overview(db: AsyncSession, user_id: uuid.UUID, case_id: uuid.UUID) -> CaseOverview:
    """Build a read-only coherent CaseOverview from the canonical Discovery Case.

    Raises ValueError if the user does not own the case or the case does not exist.
    The caller is responsible for surfacing a stale/reload state to the caller.

    This function does NOT create or modify any persistent state.
    """
    from app.discovery.authorization import require_owned_case
    from app.discovery.service import case_to_read
    from app.models.discovery import DiscoveryCase
    from app.models.enums import DiscoveryCaseStatus

    # Load canonical Case with authorization check
    raw_case = await db.get(DiscoveryCase, case_id)
    if raw_case is None or raw_case.user_id != user_id:
        raise ValueError("Case not found")
    case = await require_owned_case(db, case_id, user_id)

    # Get the full Case read (this is the canonical source of truth)
    case_read = await case_to_read(db, case)

    # ── Atomic Case rule ───────────────────────────────────────────────────────
    # snapshot_id and case_version come from the same turn_state to ensure
    # all rendered sections refer to a single coherent Case version.
    snapshot_id: str | None = None
    case_version: str | None = None
    contradictions: list[str] = []
    what_changed: list[str] = []
    unknowns: list[str] = []

    if case_read.turn_state is not None:
        snapshot_id = case_read.turn_state.snapshot_id
        case_version = (
            str(case_read.turn_state.case_version)
            if case_read.turn_state.case_version is not None
            else None
        )
        contradictions = list(case_read.turn_state.contradictions or [])
        what_changed = list(case_read.turn_state.what_changed or [])
        unknowns = list(case_read.turn_state.unknowns or [])

    # ── Findings ───────────────────────────────────────────────────────────────
    findings: list[CaseOverviewFinding] = []
    for f in case_read.findings:
        findings.append(
            CaseOverviewFinding(
                kind=f.kind,
                name=f.name,
                value=f.value,
                status=f.status,
                source=f.source,
                provenance=_finding_provenance(f.source, f.kind, f.value),
                why_this_is_here=None,  # provenance in discovery is implicit from source
            )
        )

    # ── Concerns ───────────────────────────────────────────────────────────────
    # Cluster findings by kind into concerns.
    concerns_map: dict[str, list[CaseOverviewFinding]] = {}
    for f in findings:
        if f.kind in {"concern", "symptom", "context"}:
            key = f.kind
        elif f.kind == "lab":
            key = "lab_result"
        elif f.kind == "medication":
            key = "medication"
        elif f.kind == "supplement":
            key = "supplement"
        else:
            key = "other"
        concerns_map.setdefault(key, []).append(f)

    concern_labels: dict[str, str] = {
        "concern": "Reported Concerns",
        "symptom": "Symptoms",
        "context": "Clinical Context",
        "lab_result": "Lab Results",
        "medication": "Medications",
        "supplement": "Supplements",
        "other": "Other Findings",
    }

    concerns: list[CaseOverviewConcern] = []
    for key, fitems in concerns_map.items():
        if key == "other":
            continue
        # Concern resolution is governed by Case/branch lifecycle logic (hypothesis status,
        # DiscoveryOutcome). My Case is a read-only projection — it must NOT decide resolution.
        # Status is set only from explicit governed signals; otherwise it remains "unknown".
        status = "unknown"
        if fitems:
            governed_resolved = [f for f in fitems if f.status == "resolved"]
            if all(f.status == "resolved" for f in fitems):
                # All findings are explicitly marked resolved by governed lifecycle
                status = "resolved"
            elif any(f.status == "resolved" for f in fitems):
                status = "addressed"
            # NOTE: A collection of "normal" findings does NOT automatically resolve a concern.
            # Normal findings are evidence, not resolution. The branch/coverage lifecycle engine
            # owns resolution. My Case projects; it does not decide.
        concerns.append(
            CaseOverviewConcern(
                label=concern_labels.get(key, key.title()),
                findings=fitems,
                status=status,
            )
        )

    # ── Open branches ─────────────────────────────────────────────────────────
    open_branches: list[CaseOverviewBranch] = []
    branch_tests: dict[str, list[str]] = {}
    for bc in case_read.branch_coverage:
        branch_tests.setdefault(bc.branch, []).append(bc.label)

    for h in case_read.hypotheses:
        if h.status in {"open", "active", "pending"}:
            open_branches.append(
                CaseOverviewBranch(
                    branch=h.branch,
                    label=h.label,
                    status="open",
                    tests_conducted=branch_tests.get(h.branch, []),
                )
            )

    # ── Evidence gaps ─────────────────────────────────────────────────────────
    gaps: list[CaseOverviewGap] = []
    gap_concepts: set[str] = set()
    for h in case_read.hypotheses:
        for marker in h.missing_markers:
            if marker not in gap_concepts:
                gap_concepts.add(marker)
                severity = "critical" if h.status == "open" else "minor"
                gaps.append(CaseOverviewGap(concept=marker, severity=severity))

    # Also surface unknowns as minor gaps
    for u in unknowns:
        if u not in gap_concepts:
            gap_concepts.add(u)
            gaps.append(CaseOverviewGap(concept=u, severity="minor"))

    # ── Coverage explanations ─────────────────────────────────────────────────
    # Use governed coverage semantics from the coverage catalog/governor, NOT derived
    # from arbitrary percentage thresholds. The coverage engine owns epistemic
    # relationships; My Case is a projection and must not invent semantics.
    from app.intelligence.measurements import assess_coverage as _assess_coverage
    from app.intelligence.measurements import explain_coverage as _explain_coverage

    coverage_explanations: list[CaseOverviewCoverageExplanation] = []
    for bc in case_read.branch_coverage:
        # Resolve test_code from the branch_coverage label using the coverage catalog
        from app.intelligence.measurements import test_known

        test_code = test_known(bc.label) or bc.label
        assessment = _assess_coverage(test_code, bc.branch)
        # assessment.relation is the governed semantic from the coverage catalog
        governed_relation = assessment.relation.value if hasattr(assessment.relation, "value") else str(assessment.relation)
        governed_message = assessment.explanation or _explain_coverage(bc.label, bc.branch, governed_relation)
        coverage_explanations.append(
            CaseOverviewCoverageExplanation(
                branch=bc.branch,
                relation=governed_relation,
                test_concepts=[bc.label],
                message=governed_message,
            )
        )

    # ── Next best action ─────────────────────────────────────────────────────
    next_best_action: dict | None = None
    if case_read.action_plan is not None and isinstance(case_read.action_plan, dict):
        next_best_action = case_read.action_plan

    # ── Prior workup ─────────────────────────────────────────────────────────
    prior_workup: list[dict] = list(case_read.prior_workup or [])

    # ── Data completeness ─────────────────────────────────────────────────────
    data_completeness = CaseOverviewDataCompleteness(
        investigation_coverage_percent=case_read.investigation_coverage_percent,
        total_findings=len(findings),
        total_hypotheses=len(case_read.hypotheses),
        open_branches=len(open_branches),
        unresolved_gaps=len(gaps),
    )

    unresolved_count = len(gaps) + len(open_branches) + len(contradictions)

    # ── Permissions ───────────────────────────────────────────────────────────
    permissions: dict = {
        "can_investigate": case_read.status == DiscoveryCaseStatus.OPEN.value,
        "can_export": True,
        "can_monitor": True,
    }

    # ── Feature flags ─────────────────────────────────────────────────────────
    feature_flags: dict[str, bool] = {
        "personal_evidence_regimen_v1": _is_pe_regimen_enabled(),
        "case_overview_v1": _is_case_overview_enabled(),
    }

    return CaseOverview(
        case_id=case_id,
        case_version=case_version,
        snapshot_id=snapshot_id,
        generated_at=case.updated_at or case.created_at,
        presenting_concern=case_read.presenting_concern,
        status=case_read.status.value if hasattr(case_read.status, "value") else str(case_read.status),
        concerns=concerns,
        current_findings=findings,
        prior_workup=prior_workup,
        open_branches=open_branches,
        evidence_gaps=gaps,
        contradictions=contradictions,
        coverage_explanations=coverage_explanations,
        next_best_action=next_best_action,
        what_changed=what_changed,
        data_completeness=data_completeness,
        unresolved_count=unresolved_count,
        permissions=permissions,
        feature_flags=feature_flags,
    )