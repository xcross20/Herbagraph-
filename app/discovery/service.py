"""Persist Case snapshots. Engine stays pure; this layer owns the database."""

from __future__ import annotations

import json
import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.discovery.conversation import answer_preface, compose_system_reply, parse_turn_answer
from app.discovery.engine import CaseSnapshot, FindingDraft, describe_rebuild_changes, rebuild_case_state
from app.models.discovery import (
    DiscoveryCase,
    DiscoveryFinding,
    DiscoveryHypothesis,
    DiscoveryOutcome,
    DiscoveryTurn,
)
from app.models.enums import (
    DiscoveryCaseStatus,
    DiscoveryFindingKind,
    DiscoveryHypothesisStatus,
    DiscoveryOutcomeStatus,
    DiscoveryTurnRole,
    LabResultStatus,
    PatientContextType,
    UserRole,
)
from app.models.lab import LabReport, LabResult
from app.models.patient import Patient
from app.models.patient_context import PatientContext
from app.models.user import HealthProfile, User
from app.schemas.discovery import (
    BranchCoverageRead,
    DiscoveryCaseRead,
    DiscoveryFindingRead,
    DiscoveryHypothesisRead,
    DiscoveryInvestigationRead,
    DiscoveryOutcomeRead,
    DiscoveryQuestionRead,
    DiscoveryTurnRead,
    LabIngest,
    MonitorItemRead,
)
from app.schemas.pipeline import NormalizedLabResult


def labs_from_ingest(rows: list[LabIngest]) -> list[NormalizedLabResult]:
    return [
        NormalizedLabResult(
            biomarker_name=row.biomarker_name,
            raw_test_name=row.biomarker_name,
            value=row.value,
            unit=row.unit,
            status=row.status,
            category=None,
        )
        for row in rows
    ]


def labs_from_results(rows: list[LabResult]) -> list[NormalizedLabResult]:
    return [
        NormalizedLabResult(
            biomarker_name=row.biomarker_name,
            raw_test_name=row.raw_test_name or row.biomarker_name,
            value=row.value,
            unit=row.unit,
            status=row.status,
            category=None,
        )
        for row in rows
    ]


def _percent(score: float) -> int:
    return int(round(max(0.0, min(1.0, score)) * 100))


def _question_reads(questions) -> list[DiscoveryQuestionRead]:
    return [
        DiscoveryQuestionRead(
            code=item.code,
            prompt=item.prompt,
            kind=item.kind,
            closes=item.closes,
            hypothesis_code=item.hypothesis_code,
            utility=item.utility,
        )
        for item in questions
    ]


def snapshot_to_read(
    case: DiscoveryCase,
    snapshot: CaseSnapshot,
    *,
    outcomes: list[DiscoveryOutcome] | None = None,
    turns: list[DiscoveryTurn] | None = None,
) -> DiscoveryCaseRead:
    outcome_rows = outcomes if outcomes is not None else list(case.__dict__.get("outcomes") or [])
    turn_rows = turns if turns is not None else list(case.__dict__.get("turns") or [])
    return DiscoveryCaseRead(
        id=case.id,
        presenting_concern=case.presenting_concern,
        status=case.status,
        patient_id=case.patient_id,
        lab_report_id=case.lab_report_id,
        investigation_coverage=snapshot.investigation_coverage,
        investigation_coverage_percent=_percent(snapshot.investigation_coverage),
        findings=[
            DiscoveryFindingRead(
                kind=item.kind,
                name=item.name,
                value=item.value,
                status=item.status,
                source=item.source,
            )
            for item in snapshot.findings
        ],
        hypotheses=[
            DiscoveryHypothesisRead(
                code=item.code,
                label=item.label,
                branch=item.branch,
                status=item.status,
                investigation_relevance=item.investigation_relevance,
                diagnostic_certainty=item.diagnostic_certainty,
                investigation_coverage=item.investigation_coverage,
                investigation_relevance_percent=_percent(item.investigation_relevance),
                diagnostic_certainty_percent=_percent(item.diagnostic_certainty),
                investigation_coverage_percent=_percent(item.investigation_coverage),
                why_limited=item.why_limited,
                missing_markers=item.missing_markers,
                investigations=[
                    DiscoveryInvestigationRead(
                        label=inv.label,
                        group=inv.group,
                        already_assessed=inv.already_assessed,
                    )
                    for inv in item.investigations
                ],
                not_a_diagnosis=item.not_a_diagnosis,
            )
            for item in snapshot.hypotheses
        ],
        branch_coverage=[
            BranchCoverageRead(
                branch=row.branch,
                label=row.label,
                coverage=row.coverage,
                coverage_percent=_percent(row.coverage),
                assessed=row.assessed,
                expected=row.expected,
            )
            for row in snapshot.branch_coverage
        ],
        monitor_plan=[
            MonitorItemRead(
                label=item.label,
                group=item.group,
                hypothesis_code=item.hypothesis_code,
                reason=item.reason,
            )
            for item in snapshot.monitor_plan
        ],
        next_questions=_question_reads(snapshot.next_questions),
        current_question=_question_reads(snapshot.next_questions[:1])[0] if snapshot.next_questions else None,
        what_changed=list(snapshot.what_changed),
        outcomes=[
            DiscoveryOutcomeRead(
                id=row.id,
                hypothesis_code=row.hypothesis_code,
                label=row.label,
                status=row.status,
                result=row.result,
                question_code=row.question_code,
            )
            for row in sorted(outcome_rows, key=lambda item: item.created_at)
        ],
        turns=[
            DiscoveryTurnRead(
                id=row.id,
                role=row.role,
                text=row.text,
                kind=row.kind,
                question_code=row.question_code,
                created_at=row.created_at,
            )
            for row in sorted(turn_rows, key=lambda item: item.created_at)
        ],
        disclaimer=snapshot.disclaimer,
        created_at=case.created_at,
        updated_at=case.updated_at,
    )


async def apply_snapshot(db: AsyncSession, case: DiscoveryCase, snapshot: CaseSnapshot) -> None:
    case.presenting_concern = snapshot.presenting_concern
    case.investigation_coverage = snapshot.investigation_coverage
    case.snapshot = json.dumps(snapshot.as_dict())
    if case.id is not None:
        await db.execute(delete(DiscoveryFinding).where(DiscoveryFinding.case_id == case.id))
        await db.execute(delete(DiscoveryHypothesis).where(DiscoveryHypothesis.case_id == case.id))
        await db.flush()
    for item in snapshot.findings:
        db.add(
            DiscoveryFinding(
                case_id=case.id,
                kind=DiscoveryFindingKind(item.kind),
                name=item.name,
                value=item.value,
                status=item.status,
                branch=item.branch,
                source=item.source,
            )
        )
    for item in snapshot.hypotheses:
        db.add(
            DiscoveryHypothesis(
                case_id=case.id,
                code=item.code,
                label=item.label,
                branch=item.branch,
                status=DiscoveryHypothesisStatus.OPEN,
                investigation_relevance=item.investigation_relevance,
                diagnostic_certainty=item.diagnostic_certainty,
                investigation_coverage=item.investigation_coverage,
                rationale="; ".join(item.why_limited),
                missing_markers=json.dumps(item.missing_markers),
                investigations=json.dumps([inv.__dict__ for inv in item.investigations]),
            )
        )


async def _profile_for_user(db: AsyncSession, user_id: uuid.UUID) -> dict:
    result = await db.execute(select(HealthProfile).where(HealthProfile.user_id == user_id))
    profile = result.scalar_one_or_none()
    if profile is None:
        return {}
    return {
        "age_range": profile.age_range,
        "biological_sex": profile.biological_sex,
        "current_medications": profile.current_medications or [],
        "known_conditions": profile.known_conditions or [],
        "current_supplements": profile.current_supplements or [],
        "health_goals": profile.health_goals or [],
    }


def _context_name(item: PatientContext) -> str:
    if item.value:
        return f"{item.name} ({item.value})"
    return item.name


async def _profile_from_patient(db: AsyncSession, patient_id: uuid.UUID) -> dict:
    result = await db.execute(select(Patient).where(Patient.id == patient_id))
    patient = result.scalar_one_or_none()
    if patient is None:
        return {}
    profile: dict = {}
    if patient.age is not None:
        profile["age_range"] = str(patient.age)
    if patient.biological_sex:
        profile["biological_sex"] = patient.biological_sex
    ctx = await db.execute(
        select(PatientContext).where(
            PatientContext.patient_id == patient_id,
            PatientContext.active.is_(True),
        )
    )
    meds: list[str] = []
    conditions: list[str] = []
    supplements: list[str] = []
    goals: list[str] = []
    symptoms: list[str] = []
    for item in ctx.scalars():
        if item.context_type == PatientContextType.MEDICATION:
            meds.append(_context_name(item))
        elif item.context_type == PatientContextType.CONDITION:
            conditions.append(_context_name(item))
        elif item.context_type == PatientContextType.SUPPLEMENT:
            supplements.append(_context_name(item))
        elif item.context_type == PatientContextType.GOAL:
            goals.append(_context_name(item))
        elif item.context_type == PatientContextType.SYMPTOM:
            symptoms.append(_context_name(item))
    if meds:
        profile["current_medications"] = meds
    if conditions:
        profile["known_conditions"] = conditions
    if supplements:
        profile["current_supplements"] = supplements
    if goals:
        profile["health_goals"] = goals
    if symptoms:
        profile["presenting_symptoms"] = symptoms
    return profile


_CLINICIAN_ROLES = {UserRole.CLINICIAN, UserRole.ORGANIZATION_ADMIN, UserRole.ADMIN}


async def _profile_for_case(db: AsyncSession, case: DiscoveryCase) -> dict:
    """Clinician cases use the patient record only. Personal cases may fill gaps from Self profile."""
    owner = await db.get(User, case.user_id)
    patient_profile = await _profile_from_patient(db, case.patient_id) if case.patient_id else {}
    if owner is not None and owner.role in _CLINICIAN_ROLES:
        return patient_profile
    user_profile = await _profile_for_user(db, case.user_id)
    merged = dict(user_profile)
    for key, value in patient_profile.items():
        if value:
            merged[key] = value
    return merged


async def latest_lab_report(db: AsyncSession, user_id: uuid.UUID, patient_id: uuid.UUID | None) -> LabReport | None:
    query = select(LabReport).where(LabReport.user_id == user_id).order_by(LabReport.created_at.desc())
    if patient_id is not None:
        query = query.where(LabReport.patient_id == patient_id)
    result = await db.execute(query.limit(1))
    return result.scalar_one_or_none()


async def create_case(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    presenting_concern: str,
    patient_id: uuid.UUID | None = None,
) -> DiscoveryCase:
    case = DiscoveryCase(
        user_id=user_id,
        patient_id=patient_id,
        presenting_concern=presenting_concern.strip(),
        status=DiscoveryCaseStatus.OPEN,
    )
    db.add(case)
    await db.flush()
    return case


def _case_load_options():
    return (
        selectinload(DiscoveryCase.findings),
        selectinload(DiscoveryCase.hypotheses),
        selectinload(DiscoveryCase.outcomes),
        selectinload(DiscoveryCase.turns),
    )


async def get_owned_case(db: AsyncSession, case_id: uuid.UUID, user_id: uuid.UUID) -> DiscoveryCase | None:
    result = await db.execute(
        select(DiscoveryCase)
        .where(DiscoveryCase.id == case_id, DiscoveryCase.user_id == user_id)
        .options(*_case_load_options())
    )
    return result.scalar_one_or_none()


async def list_owned_cases(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    patient_id: uuid.UUID | None = None,
) -> list[DiscoveryCase]:
    query = select(DiscoveryCase).where(DiscoveryCase.user_id == user_id)
    if patient_id is not None:
        query = query.where(DiscoveryCase.patient_id == patient_id)
    result = await db.execute(
        query.options(*_case_load_options()).order_by(DiscoveryCase.updated_at.desc())
    )
    return list(result.scalars().all())


def _parse_lab_value(raw: str | None) -> tuple[float, str | None]:
    if not raw:
        return 0.0, None
    parts = raw.strip().split(None, 1)
    try:
        value = float(parts[0])
    except ValueError:
        return 0.0, raw
    return value, parts[1] if len(parts) > 1 else None


def labs_from_snapshot(snapshot: CaseSnapshot) -> list[NormalizedLabResult]:
    rows: list[NormalizedLabResult] = []
    for item in snapshot.findings:
        if item.kind != "lab":
            continue
        value, unit = _parse_lab_value(item.value)
        try:
            status = LabResultStatus(item.status) if item.status else LabResultStatus.NORMAL
        except ValueError:
            status = LabResultStatus.NORMAL
        rows.append(
            NormalizedLabResult(
                biomarker_name=item.name,
                raw_test_name=item.name,
                value=value,
                unit=unit,
                status=status,
                category=None,
            )
        )
    return rows


def _draft_from_finding(item: DiscoveryFinding) -> FindingDraft:
    return FindingDraft(
        kind=item.kind.value if hasattr(item.kind, "value") else str(item.kind),
        name=item.name,
        value=item.value,
        status=item.status,
        branch=item.branch,
        source=item.source,
    )


async def _assessment_state(db: AsyncSession, case: DiscoveryCase) -> tuple[list[str], list[str], list[FindingDraft]]:
    assessed: list[str] = []
    answered: list[str] = []
    extras: list[FindingDraft] = []
    seen_notes: set[tuple[str, str | None]] = set()
    if case.id is None:
        return assessed, answered, extras
    findings = (
        await db.execute(select(DiscoveryFinding).where(DiscoveryFinding.case_id == case.id))
    ).scalars().all()
    outcomes = (
        await db.execute(select(DiscoveryOutcome).where(DiscoveryOutcome.case_id == case.id))
    ).scalars().all()
    for item in findings:
        if item.kind == DiscoveryFindingKind.ASSESSMENT:
            extras.append(_draft_from_finding(item))
            answered.append(item.name)
            if item.value == "already_assessed":
                assessed.append(item.name)
        elif item.kind == DiscoveryFindingKind.CONTEXT and item.name == "Additional note":
            key = (item.name, item.value)
            if key in seen_notes:
                continue
            seen_notes.add(key)
            extras.append(_draft_from_finding(item))
    for row in outcomes:
        answered.append(row.label)
        if row.status == DiscoveryOutcomeStatus.COMPLETED:
            assessed.append(row.label)
    return assessed, answered, extras


async def add_turn(
    db: AsyncSession,
    case: DiscoveryCase,
    *,
    role: DiscoveryTurnRole,
    text: str,
    kind: str,
    question_code: str | None = None,
) -> DiscoveryTurn:
    turn = DiscoveryTurn(
        case_id=case.id,
        role=role,
        text=text,
        kind=kind,
        question_code=question_code,
    )
    db.add(turn)
    await db.flush()
    return turn


async def add_system_reply(
    db: AsyncSession,
    case: DiscoveryCase,
    snapshot: CaseSnapshot,
    *,
    preface: str | None = None,
) -> DiscoveryTurn:
    text, question_code = compose_system_reply(snapshot, preface=preface)
    return await add_turn(
        db,
        case,
        role=DiscoveryTurnRole.SYSTEM,
        text=text,
        kind="question" if question_code else "system",
        question_code=question_code,
    )


async def rebuild_case(
    db: AsyncSession,
    case: DiscoveryCase,
    *,
    presenting_concern: str | None = None,
    labs: list[NormalizedLabResult] | None = None,
    lab_report_id: uuid.UUID | None = None,
) -> CaseSnapshot:
    if presenting_concern is not None and presenting_concern.strip():
        case.presenting_concern = presenting_concern.strip()
    if lab_report_id is not None:
        case.lab_report_id = lab_report_id
    profile = await _profile_for_case(db, case)
    previous = snapshot_from_case(case) if case.snapshot else None
    if not labs:
        labs = labs_from_snapshot(previous) if previous else []
    assessed, answered, extras = await _assessment_state(db, case)
    snapshot = rebuild_case_state(
        case.presenting_concern,
        labs,
        profile,
        extra_assessed=assessed,
        answered_labels=answered,
        extra_findings=extras,
    )
    snapshot.what_changed = describe_rebuild_changes(previous, snapshot)
    await apply_snapshot(db, case, snapshot)
    await db.flush()
    return snapshot


def _question_from_snapshot(snapshot: CaseSnapshot, code: str):
    for question in snapshot.next_questions:
        if question.code == code:
            return question
    return None


async def answer_question(
    db: AsyncSession,
    case: DiscoveryCase,
    *,
    code: str,
    answer: str,
    note: str | None = None,
    spoken: str | None = None,
) -> CaseSnapshot:
    snapshot = snapshot_from_case(case)
    question = _question_from_snapshot(snapshot, code)
    if question is None:
        raise ValueError("That question is no longer open on this case.")
    status = {
        "yes": DiscoveryOutcomeStatus.COMPLETED,
        "no": DiscoveryOutcomeStatus.NOT_DONE,
        "unknown": DiscoveryOutcomeStatus.PENDING,
    }[answer]
    db.add(
        DiscoveryOutcome(
            case_id=case.id,
            hypothesis_code=question.hypothesis_code,
            label=question.closes,
            status=status,
            result=note,
            question_code=question.code,
        )
    )
    db.add(
        DiscoveryFinding(
            case_id=case.id,
            kind=DiscoveryFindingKind.ASSESSMENT,
            name=question.closes,
            value="already_assessed" if answer == "yes" else answer,
            status=None,
            branch=None,
            source="user",
        )
    )
    await db.flush()
    await add_turn(
        db,
        case,
        role=DiscoveryTurnRole.USER,
        text=spoken or {"yes": "Yes", "no": "No", "unknown": "Not sure"}[answer],
        kind="answer",
        question_code=question.code,
    )
    updated = await rebuild_case(db, case)
    await add_system_reply(db, case, updated, preface=answer_preface(answer))
    return updated


async def record_user_note(db: AsyncSession, case: DiscoveryCase, text: str) -> CaseSnapshot:
    db.add(
        DiscoveryFinding(
            case_id=case.id,
            kind=DiscoveryFindingKind.CONTEXT,
            name="Additional note",
            value=text.strip(),
            status=None,
            branch=None,
            source="user",
        )
    )
    await add_turn(db, case, role=DiscoveryTurnRole.USER, text=text.strip(), kind="note")
    await db.flush()
    snapshot = await rebuild_case(db, case)
    await add_system_reply(db, case, snapshot)
    return snapshot


async def apply_user_turn(db: AsyncSession, case: DiscoveryCase, text: str) -> CaseSnapshot:
    """Typed chat: a bare yes/no answers the current question; anything else is a note."""
    parsed = parse_turn_answer(text)
    snapshot = snapshot_from_case(case)
    current = snapshot.next_questions[0] if snapshot.next_questions else None
    if parsed and current is not None:
        return await answer_question(db, case, code=current.code, answer=parsed, spoken=text.strip())
    return await record_user_note(db, case, text)


def snapshot_from_case(case: DiscoveryCase) -> CaseSnapshot:
    if case.snapshot:
        return CaseSnapshot.from_dict(json.loads(case.snapshot))
    return rebuild_case_state(case.presenting_concern, [], {})


async def case_to_read(db: AsyncSession, case: DiscoveryCase) -> DiscoveryCaseRead:
    outcomes = (
        await db.execute(select(DiscoveryOutcome).where(DiscoveryOutcome.case_id == case.id))
    ).scalars().all()
    turns = (
        await db.execute(select(DiscoveryTurn).where(DiscoveryTurn.case_id == case.id))
    ).scalars().all()
    return snapshot_to_read(case, snapshot_from_case(case), outcomes=list(outcomes), turns=list(turns))
