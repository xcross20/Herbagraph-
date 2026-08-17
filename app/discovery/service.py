"""Persist Case snapshots. Engine stays pure; this layer owns the database."""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import attributes, selectinload

from app.discovery.actions import QUESTIONS
from app.discovery.conversation import answer_preface, compose_system_reply
from app.discovery.engine import CaseSnapshot, FindingDraft, describe_rebuild_changes, rebuild_case_state
from app.discovery.map import build_map_payload, payload_fingerprint, unknowns_from_facts
from app.discovery.mutations import apply_finding_drafts
from app.discovery.orchestrator import facts_from_findings
from app.models.discovery import (
    DiscoveryCase,
    DiscoveryFinding,
    DiscoveryHypothesis,
    DiscoveryMapVersion,
    DiscoveryOutcome,
    DiscoveryTestPlanItem,
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
    DiscoveryActionRead,
    DiscoveryInteractionRead,
    DiscoveryQuestionRead,
    DiscoveryTurnRead,
    DiscoveryTurnStateRead,
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


def _literature_from_case(case: DiscoveryCase) -> list[dict]:
    raw = getattr(case, "literature_json", None)
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def _provenance(item: FindingDraft) -> str:
    value = (item.value or "").lower()
    if "unverified" in value or value in {"mentioned", "reported_normal", "reported_abnormal"}:
        return "reported"
    if item.source == "lab_engine":
        return "verified"
    if item.kind == "assessment" and value == "already_assessed":
        return "reported"
    if item.source == "intake":
        return "reported"
    return "inferred"


def _memory_items_from_findings(findings: list[FindingDraft]) -> list[dict]:
    items = []
    for item in findings:
        if item.kind in {"concern"}:
            continue
        items.append(
            {
                "name": item.name,
                "value": item.value,
                "kind": item.kind,
                "provenance": _provenance(item),
            }
        )
    return items[:24]


def _timeline_from_findings(findings: list[FindingDraft]) -> list[dict]:
    rows = []
    for item in findings:
        if item.name in {"duration", "onset", "timing"}:
            rows.append({"name": item.name, "value": item.value, "provenance": _provenance(item)})
    return rows


def _prior_workup_from_findings(findings: list[FindingDraft]) -> list[dict]:
    rows = []
    for item in findings:
        if item.name in {"claimed normal labs", "emg testing", "prior_workup", "radiology report", "clinical note"}:
            rows.append(
                {
                    "name": item.name,
                    "value": item.value,
                    "verification": "patient_reported",
                    "provenance": "reported",
                }
            )
    return rows


async def persist_map_version(db: AsyncSession, case: DiscoveryCase, snapshot: CaseSnapshot) -> DiscoveryMapVersion:
    persisted = list(
        (
            await db.execute(select(DiscoveryFinding).where(DiscoveryFinding.case_id == case.id))
        ).scalars()
    )
    findings = [row for row in persisted if getattr(row, "active", True)] if persisted else snapshot.findings
    facts = facts_from_findings(findings)
    payload = build_map_payload(
        snapshot=snapshot,
        facts=facts,
        unknowns=unknowns_from_facts(facts),
        findings=findings,
    )
    fingerprint = payload_fingerprint(payload)
    existing = (
        await db.execute(
            select(DiscoveryMapVersion)
            .where(DiscoveryMapVersion.case_id == case.id)
            .order_by(DiscoveryMapVersion.version.desc())
        )
    ).scalars().first()
    if existing is not None and existing.fingerprint == fingerprint:
        case._map_version = existing.version
        return existing
    version = 1 if existing is None else existing.version + 1
    row = DiscoveryMapVersion(
        case_id=case.id,
        version=version,
        fingerprint=fingerprint,
        payload=json.dumps(payload),
    )
    db.add(row)
    await db.flush()
    case._map_version = version
    return row


def _question_reads(questions) -> list[DiscoveryQuestionRead]:
    return [
        DiscoveryQuestionRead(
            code=item.code,
            prompt=item.prompt,
            kind=item.kind,
            closes=item.closes,
            hypothesis_code=getattr(item, "hypothesis_code", "") or "",
            utility=getattr(item, "utility", 0.0) or 0.0,
            options=list(getattr(item, "options", ()) or []),
        )
        for item in questions
    ]


def _closes_for_question(code: str | None) -> str | None:
    if not code:
        return None
    for question in QUESTIONS:
        if question.code == code:
            return question.closes
    return None


def _payload_dict(turn: DiscoveryTurn) -> dict:
    if not turn.payload:
        return {}
    try:
        raw = json.loads(turn.payload)
    except json.JSONDecodeError:
        return {}
    return raw if isinstance(raw, dict) else {}


def _last_system_payload(turns: list[DiscoveryTurn]) -> dict:
    last = None
    for turn in sorted(turns, key=lambda item: item.created_at):
        if turn.role == DiscoveryTurnRole.SYSTEM and turn.payload:
            last = turn
    return _payload_dict(last) if last is not None else {}


def snapshot_to_read(
    case: DiscoveryCase,
    snapshot: CaseSnapshot,
    *,
    outcomes: list[DiscoveryOutcome] | None = None,
    turns: list[DiscoveryTurn] | None = None,
) -> DiscoveryCaseRead:
    outcome_rows = outcomes if outcomes is not None else list(case.__dict__.get("outcomes") or [])
    turn_rows = turns if turns is not None else list(case.__dict__.get("turns") or [])
    payload = _last_system_payload(turn_rows)
    action_raw = payload.get("action") or {}
    interaction_raw = payload.get("interaction") or action_raw.get("interaction")
    current_from_action = None
    if action_raw.get("type") == "ask_question" and action_raw.get("question_id"):
        current_from_action = DiscoveryQuestionRead(
            code=action_raw["question_id"],
            prompt=action_raw.get("prompt") or "",
            kind="discriminating",
            closes=_closes_for_question(action_raw.get("question_id")) or "",
            hypothesis_code="",
            utility=float(action_raw.get("score") or 0.0),
            options=list((interaction_raw or {}).get("options") or []),
        )
    turn_state = None
    if payload.get("stage") and action_raw.get("type"):
        from app.discovery.safety import normalize_state

        safety_raw = payload.get("safety") if isinstance(payload.get("safety"), dict) else {}
        turn_state = DiscoveryTurnStateRead(
            stage=str(payload.get("stage") or case.stage or "opening"),
            safety_status=normalize_state(str(payload.get("safety_status") or safety_raw.get("state") or "S0")),
            intents=list(payload.get("intents") or []),
            selected_action=DiscoveryActionRead(
                type=str(action_raw.get("type")),
                objective=str(action_raw.get("objective") or ""),
                question_id=action_raw.get("question_id"),
                prompt=action_raw.get("prompt"),
            ),
            problem_representation=str(payload.get("problem_representation") or case.problem_representation or ""),
            unknowns=list(payload.get("unknowns") or []),
            contradictions=list(payload.get("contradictions") or []),
            what_changed=list(payload.get("what_changed") or []),
            critic=str(payload.get("critic") or ""),
            safety_evidence_status=safety_raw.get("evidence_status"),
            safety_confidence=safety_raw.get("confidence"),
            safety_override=bool(payload.get("safety_override") or safety_raw.get("override")),
            discovery_can_continue=payload.get("discovery_can_continue", safety_raw.get("discovery_can_continue", True)),
            clinical_followup_needed=bool(
                payload.get("clinical_followup_needed") or safety_raw.get("clinical_followup_needed")
            ),
            safety_net=safety_raw.get("safety_net"),
        )
    interaction = None
    if isinstance(interaction_raw, dict) and interaction_raw.get("type"):
        interaction = DiscoveryInteractionRead(
            type=str(interaction_raw.get("type")),
            options=list(interaction_raw.get("options") or []),
            accepted_types=list(interaction_raw.get("accepted_types") or []),
        )
    active_findings = _active_findings_for_read(case, snapshot)
    from app.discovery.tripwires import evaluate_finding_projection

    evaluate_finding_projection(list(case.__dict__.get("findings") or []) or list(active_findings))
    facts = facts_from_findings(active_findings)
    unknowns = list(payload.get("unknowns") or unknowns_from_facts(facts))
    map_payload = build_map_payload(
        snapshot=snapshot,
        facts=facts,
        unknowns=unknowns,
        findings=active_findings,
    )
    map_version = getattr(case, "_map_version", None)
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
            for item in active_findings
        ],
        hypotheses=[
            DiscoveryHypothesisRead(
                code=item.code,
                label=item.label,
                branch=item.branch,
                status=item.status,
                investigation_relevance=item.investigation_relevance,
                investigation_coverage=item.investigation_coverage,
                investigation_relevance_percent=_percent(item.investigation_relevance),
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
        current_question=current_from_action
        or (_question_reads(snapshot.next_questions[:1])[0] if snapshot.next_questions else None),
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
        stage=getattr(case, "stage", None) or "opening",
        problem_representation=getattr(case, "problem_representation", None),
        interaction=interaction,
        turn_state=turn_state,
        investigation_map=map_payload,
        map_version=map_version,
        confidence_increasers=map_payload.get("confidence_increasers") or [],
        timeline=_timeline_from_findings(snapshot.findings),
        prior_workup=_prior_workup_from_findings(snapshot.findings),
        memory_items=_memory_items_from_findings(snapshot.findings),
        literature=_literature_from_case(case),
        safety=payload.get("safety") if isinstance(payload.get("safety"), dict) else None,
        last_visit=None,
        disclaimer=snapshot.disclaimer,
        created_at=case.created_at,
        updated_at=case.updated_at,
    )


async def apply_snapshot(
    db: AsyncSession,
    case: DiscoveryCase,
    snapshot: CaseSnapshot,
    *,
    source_event_id: str | None = None,
) -> None:
    case.presenting_concern = snapshot.presenting_concern
    case.investigation_coverage = snapshot.investigation_coverage
    case.snapshot = json.dumps(snapshot.as_dict())
    if case.id is not None:
        event_id = source_event_id or str(uuid.uuid4())
        await apply_finding_drafts(db, case.id, snapshot.findings, source_event_id=event_id)
        await db.execute(delete(DiscoveryHypothesis).where(DiscoveryHypothesis.case_id == case.id))
        await db.flush()
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
        elif item.kind == DiscoveryFindingKind.SYMPTOM:
            extras.append(_draft_from_finding(item))
        elif item.kind == DiscoveryFindingKind.CONTEXT:
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
    intent: str | None = None,
    action_type: str | None = None,
    stage: str | None = None,
    payload: str | None = None,
) -> DiscoveryTurn:
    turn = DiscoveryTurn(
        case_id=case.id,
        role=role,
        text=text,
        kind=(kind or "note")[:20],
        question_code=question_code,
        intent=intent,
        action_type=action_type,
        stage=stage,
        payload=payload,
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
    if case.id is not None:
        await persist_map_version(db, case, snapshot)
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


async def _snapshot_payload(db: AsyncSession, patient_id) -> dict | None:
    from app.discovery.snapshot import current_snapshot

    snap = await current_snapshot(db, patient_id)
    if snap is None:
        return None
    try:
        data = json.loads(snap.payload)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


async def _person_context(
    db: AsyncSession,
    case: DiscoveryCase,
    *,
    prior_facts: dict[str, str],
    last_visit: dict | None,
    snapshot_payload: dict | None = None,
) -> dict:
    from app.discovery.context import person_package

    display = None
    age = None
    sex = None
    payload = snapshot_payload
    if case.patient_id:
        patient = await db.get(Patient, case.patient_id)
        if patient is not None:
            display = patient.display_name
            age = patient.age
            sex = patient.biological_sex
        if payload is None:
            payload = await _snapshot_payload(db, case.patient_id)
    return person_package(
        display_name=display,
        snapshot_payload=payload,
        prior_facts=prior_facts,
        last_visit=last_visit,
        age=age,
        biological_sex=sex,
    )


async def _attach_literature(case: DiscoveryCase, text: str, result) -> None:
    from app.discovery.ai import pick_verbalization
    from app.discovery.literature import retrieve_citations

    cites = list(result.citations or [])
    if not cites:
        plan = result.guide_plan or {}
        queries = [str(item) for item in (plan.get("literature_queries") or []) if item]
        if result.action.type == "retrieve_evidence" or plan.get("wants_evidence"):
            queries.append((case.presenting_concern or text)[:180])
        query = next((item for item in queries if len(item) >= 4), "")
        if query:
            cites = await retrieve_citations(query)
            result.citations = cites
    if not cites:
        return
    case.literature_json = json.dumps(cites)
    titles = "; ".join(item["title"][:90] for item in cites[:2] if item.get("title"))
    if titles and "pubmed" not in result.message.lower() and "pmid" not in result.message.lower():
        result.message = pick_verbalization(
            result.message,
            f"{result.message} Related published work I can actually cite: {titles}. That is not a diagnosis.",
        )


async def apply_user_turn(
    db: AsyncSession,
    case: DiscoveryCase,
    text: str,
    *,
    audience: str = "consumer",
    on_phase: Callable[..., Any] | None = None,
) -> CaseSnapshot:
    """One orchestrated turn: mutate the Case, then speak the chosen action."""
    turns = (
        await db.execute(select(DiscoveryTurn).where(DiscoveryTurn.case_id == case.id))
    ).scalars().all()
    findings = (
        await db.execute(select(DiscoveryFinding).where(DiscoveryFinding.case_id == case.id))
    ).scalars().all()
    asked = [turn.question_code for turn in turns if turn.role == DiscoveryTurnRole.SYSTEM and turn.question_code]
    answered = {item.name for item in findings if item.kind == DiscoveryFindingKind.ASSESSMENT}
    prior = facts_from_findings(findings)
    payload = _last_system_payload(list(turns))
    current_closes = _closes_for_question((payload.get("action") or {}).get("question_id"))
    from app.discovery.guide import DiscoveryGuide
    from app.discovery.snapshot import prior_facts_from_snapshot

    snap_payload = None
    if case.patient_id:
        snap_payload = await _snapshot_payload(db, case.patient_id)
        if snap_payload:
            prior = {**prior_facts_from_snapshot(snap_payload), **prior}
    if getattr(case, "safety_json", None):
        try:
            held = json.loads(case.safety_json)
            if isinstance(held, dict) and held.get("state"):
                prior["safety_state"] = str(held["state"])
        except json.JSONDecodeError:
            pass
    recent = [turn.text for turn in sorted(turns, key=lambda item: item.created_at)][-12:]
    last_visit = None
    if snap_payload:
        from app.discovery.context import last_visit_from_snapshot

        last_visit = last_visit_from_snapshot(snap_payload)
    person = await _person_context(
        db, case, prior_facts=prior, last_visit=last_visit, snapshot_payload=snap_payload
    )
    result = await DiscoveryGuide().process_turn(
        text,
        prior_facts=prior,
        asked=asked,
        answered=answered,
        current_closes=current_closes,
        concern=case.presenting_concern,
        audience=audience,
        turn_count=len(turns),
        recent_turns=recent,
        problem=case.problem_representation,
        on_phase=on_phase,
        last_visit=last_visit,
        person=person,
    )
    await _attach_literature(case, text, result)
    await add_turn(
        db,
        case,
        role=DiscoveryTurnRole.USER,
        text=text.strip(),
        kind="turn",
        intent=",".join(result.intents),
        stage=result.stage,
    )
    for item in result.new_findings:
        kind = item.kind if item.kind in {k.value for k in DiscoveryFindingKind} else "symptom"
        db.add(
            DiscoveryFinding(
                case_id=case.id,
                kind=DiscoveryFindingKind(kind),
                name=item.name,
                value=item.value,
                status=item.status,
                branch=item.branch,
                source=item.source,
            )
        )
    await db.flush()
    snapshot = await rebuild_case(db, case)
    await add_turn(
        db,
        case,
        role=DiscoveryTurnRole.SYSTEM,
        text=result.message,
        kind=result.action.type,
        question_code=result.action.question_id,
        intent=",".join(result.intents),
        action_type=result.action.type,
        stage=result.stage,
        payload=json.dumps(result.as_dict()),
    )
    case.stage = result.stage
    case.problem_representation = result.problem_representation
    case.safety_json = json.dumps(result.safety or {})
    if result.safety_status == "S4":
        case.status = DiscoveryCaseStatus.PAUSED
    await db.flush()
    if case.patient_id:
        from app.discovery.snapshot import generate_patient_snapshot

        try:
            await generate_patient_snapshot(db, user_id=case.user_id, patient_id=case.patient_id)
        except ValueError:
            pass
    return snapshot


async def apply_opening_turn(
    db: AsyncSession,
    case: DiscoveryCase,
    text: str,
    *,
    audience: str = "consumer",
    on_phase: Callable[..., Any] | None = None,
) -> CaseSnapshot:
    from app.discovery.guide import DiscoveryGuide
    from app.discovery.snapshot import prior_facts_from_snapshot

    snapshot = await rebuild_case(db, case)
    await add_turn(db, case, role=DiscoveryTurnRole.USER, text=text.strip(), kind="concern")
    prior: dict[str, str] = {}
    snap_payload = await _snapshot_payload(db, case.patient_id) if case.patient_id else None
    if snap_payload:
        prior = prior_facts_from_snapshot(snap_payload)
    last_visit = None
    if snap_payload:
        from app.discovery.context import last_visit_from_snapshot

        last_visit = last_visit_from_snapshot(snap_payload)
    result = await DiscoveryGuide().process_turn(
        text,
        prior_facts=prior,
        asked=[],
        answered=set(),
        concern=text,
        audience=audience,
        turn_count=0,
        problem=case.problem_representation,
        on_phase=on_phase,
        last_visit=last_visit,
        person=await _person_context(
            db, case, prior_facts=prior, last_visit=last_visit, snapshot_payload=snap_payload
        ),
    )
    await _attach_literature(case, text, result)
    for item in result.new_findings:
        kind = item.kind if item.kind in {k.value for k in DiscoveryFindingKind} else "symptom"
        db.add(
            DiscoveryFinding(
                case_id=case.id,
                kind=DiscoveryFindingKind(kind),
                name=item.name,
                value=item.value,
                status=item.status,
                branch=item.branch,
                source=item.source,
            )
        )
    await db.flush()
    snapshot = await rebuild_case(db, case)
    await add_turn(
        db,
        case,
        role=DiscoveryTurnRole.SYSTEM,
        text=result.message,
        kind=result.action.type,
        question_code=result.action.question_id,
        action_type=result.action.type,
        stage=result.stage,
        payload=json.dumps(result.as_dict()),
    )
    case.stage = result.stage
    case.problem_representation = result.problem_representation
    case.safety_json = json.dumps(result.safety or {})
    if result.safety_status == "S4":
        case.status = DiscoveryCaseStatus.PAUSED
    await db.flush()
    if case.patient_id:
        from app.discovery.snapshot import generate_patient_snapshot

        try:
            await generate_patient_snapshot(db, user_id=case.user_id, patient_id=case.patient_id)
        except ValueError:
            pass
    return snapshot


def _active_findings_for_read(case: DiscoveryCase, snapshot: CaseSnapshot):
    loaded = case.__dict__.get("findings", None)
    if loaded is not None:
        return [item for item in list(loaded) if getattr(item, "active", True)]
    return [
        item
        for item in snapshot.findings
        if getattr(item, "active", True)
    ]


def snapshot_from_case(case: DiscoveryCase) -> CaseSnapshot:
    if case.snapshot:
        return CaseSnapshot.from_dict(json.loads(case.snapshot))
    return rebuild_case_state(case.presenting_concern, [], {})


async def case_to_read(db: AsyncSession, case: DiscoveryCase) -> DiscoveryCaseRead:
    findings = (
        await db.execute(select(DiscoveryFinding).where(DiscoveryFinding.case_id == case.id))
    ).scalars().all()
    attributes.set_committed_value(case, "findings", list(findings))
    outcomes = (
        await db.execute(select(DiscoveryOutcome).where(DiscoveryOutcome.case_id == case.id))
    ).scalars().all()
    turns = (
        await db.execute(select(DiscoveryTurn).where(DiscoveryTurn.case_id == case.id))
    ).scalars().all()
    latest_map = (
        await db.execute(
            select(DiscoveryMapVersion)
            .where(DiscoveryMapVersion.case_id == case.id)
            .order_by(DiscoveryMapVersion.version.desc())
        )
    ).scalars().first()
    if latest_map is not None:
        case._map_version = latest_map.version
    read = snapshot_to_read(case, snapshot_from_case(case), outcomes=list(outcomes), turns=list(turns))
    from app.discovery.context import last_visit_from_case

    visit = last_visit_from_case(
        problem=case.problem_representation,
        workup=read.prior_workup,
        concern=case.presenting_concern,
    )
    if len(read.turns) < 2:
        visit["has_history"] = False
    read.last_visit = visit
    return read


def suggested_test_labels(snapshot: CaseSnapshot) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    seen: set[str] = set()
    for item in snapshot.monitor_plan:
        key = item.label.lower()
        if key in seen:
            continue
        seen.add(key)
        rows.append((item.label, item.reason))
    for hypo in snapshot.hypotheses:
        for marker in hypo.missing_markers[:3]:
            key = marker.lower()
            if key in seen:
                continue
            seen.add(key)
            rows.append((marker, f"Named gap on {hypo.label}."))
    return rows[:12]


async def add_case_tests_to_plan(
    db: AsyncSession,
    case: DiscoveryCase,
    user_id: uuid.UUID,
    labels: list[str] | None = None,
) -> list[DiscoveryTestPlanItem]:
    snapshot = snapshot_from_case(case)
    suggested = suggested_test_labels(snapshot)
    wanted = {item.lower() for item in labels} if labels else None
    existing = {
        row.label.lower()
        for row in (
            await db.execute(select(DiscoveryTestPlanItem).where(DiscoveryTestPlanItem.case_id == case.id))
        ).scalars()
    }
    created: list[DiscoveryTestPlanItem] = []
    for label, reason in suggested:
        if wanted is not None and label.lower() not in wanted:
            continue
        if label.lower() in existing:
            continue
        item = DiscoveryTestPlanItem(
            user_id=user_id,
            case_id=case.id,
            patient_id=case.patient_id,
            label=label,
            reason=reason,
            status="added",
            source="discovery",
        )
        db.add(item)
        created.append(item)
        existing.add(label.lower())
    await db.flush()
    return created


async def ingest_case_document(
    db: AsyncSession,
    case: DiscoveryCase,
    *,
    filename: str,
    text: str,
) -> dict:
    from app.discovery.records import classify_document, extract_record_findings

    kind = classify_document(filename, text)
    if kind == "lab":
        return {
            "kind": "lab",
            "accepted": False,
            "detail": "Use the existing lab upload in the workspace. Discovery does not replace the lab parser.",
        }
    for item in extract_record_findings(kind, text):
        finding_kind = item.kind if item.kind in {k.value for k in DiscoveryFindingKind} else "context"
        db.add(
            DiscoveryFinding(
                case_id=case.id,
                kind=DiscoveryFindingKind(finding_kind),
                name=item.name,
                value=item.value,
                source="document",
            )
        )
    await db.flush()
    await rebuild_case(db, case)
    await add_turn(
        db,
        case,
        role=DiscoveryTurnRole.SYSTEM,
        text=f"Attached {filename} as a {kind} report finding. This is not a diagnosis.",
        kind="document",
    )
    if case.patient_id:
        from app.discovery.snapshot import generate_patient_snapshot

        try:
            await generate_patient_snapshot(db, user_id=case.user_id, patient_id=case.patient_id)
        except ValueError:
            pass
    return {"kind": kind, "accepted": True, "detail": "Attached to the Case as a report finding, not a diagnosis."}


async def remove_named_finding(db: AsyncSession, case: DiscoveryCase, name: str) -> None:
    rows = (
        await db.execute(select(DiscoveryFinding).where(DiscoveryFinding.case_id == case.id))
    ).scalars().all()
    target = name.strip().lower()
    removed = False
    for item in rows:
        if item.name.lower() == target or item.name.lower().startswith(target + "_"):
            await db.delete(item)
            removed = True
    if not removed:
        raise ValueError("Finding not found")
    await db.flush()
    await rebuild_case(db, case)


async def verify_named_finding(db: AsyncSession, case: DiscoveryCase, name: str) -> None:
    rows = (
        await db.execute(select(DiscoveryFinding).where(DiscoveryFinding.case_id == case.id))
    ).scalars().all()
    target = name.strip().lower()
    found = False
    for item in rows:
        if item.name.lower() == target:
            item.status = "verified"
            if item.value and "patient_reported" in item.value:
                item.value = item.value.replace("patient_reported", "verified")
            found = True
    if not found:
        raise ValueError("Finding not found")
    await db.flush()
    await rebuild_case(db, case)


async def list_test_plan(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    patient_id: uuid.UUID | None = None,
) -> list[DiscoveryTestPlanItem]:
    query = select(DiscoveryTestPlanItem).where(DiscoveryTestPlanItem.user_id == user_id)
    if patient_id is not None:
        query = query.where(DiscoveryTestPlanItem.patient_id == patient_id)
    result = await db.execute(query.order_by(DiscoveryTestPlanItem.created_at.desc()))
    return list(result.scalars().all())
