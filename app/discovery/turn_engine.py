"""Atomic 19-step Discovery turn pipeline. One service owns the transaction."""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.discovery.coverage_governor import assess_coverage
from app.discovery.evidence_interpreter import interpret_workup
from app.discovery.intent import classify_intent
from app.discovery.lifecycle import propose_transition
from app.discovery.orchestrator import facts_from_findings
from app.discovery.resolver import resolve_test
from app.discovery.safety import assess_safety, extract_safety_findings, findings_from_fact_map
from app.discovery.scientific_output import ScientificItem, ScientificItemType, validate_scientific_output
from app.discovery.telemetry import increment
from app.models.discovery import DiscoveryCase, DiscoveryFinding, DiscoveryTurn
from app.models.enums import BranchLifecycleStatus, CoverageRelation, DiscoveryFindingKind, DiscoveryTurnRole

STAGES = (
    "authenticate",
    "resolve_source_event",
    "load_canonical",
    "normalize_input",
    "safety_screen",
    "classify_intent",
    "extract_facts",
    "detect_conflicts",
    "propose_mutations",
    "resolve_tests",
    "assess_coverage",
    "interpret_evidence",
    "apply_lifecycle",
    "generate_candidates",
    "rank_actions",
    "validate_output",
    "persist",
    "render_response",
    "emit_metrics",
)


class TurnAborted(Exception):
    """Injected failure before persist. No canonical writes."""


@dataclass
class TurnPipelineResult:
    snapshot: Any
    stages: list[str] = field(default_factory=list)
    reused: bool = False
    source_event_id: str = ""
    safety_state: str = "S0"


def _control_from_case(case: DiscoveryCase) -> dict | None:
    raw = getattr(case, "control_json", None)
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def normalize_input(text: str) -> tuple[str, str]:
    original = text or ""
    return original, " ".join(original.split()).strip()


async def _existing_turn(db: AsyncSession, case_id, key: str | None) -> DiscoveryTurn | None:
    if not key:
        return None
    return (
        await db.execute(
            select(DiscoveryTurn).where(
                DiscoveryTurn.case_id == case_id,
                DiscoveryTurn.idempotency_key == key,
                DiscoveryTurn.role == DiscoveryTurnRole.USER,
            )
        )
    ).scalar_one_or_none()


async def run_turn(
    db: AsyncSession,
    case: DiscoveryCase,
    text: str,
    *,
    audience: str = "consumer",
    idempotency_key: str | None = None,
    on_phase: Callable[..., Any] | None = None,
    fail_after: str | None = None,
    opening: bool = False,
) -> TurnPipelineResult:
    from app.discovery.guide import DiscoveryGuide
    from app.discovery.service import (
        _attach_literature,
        _closes_for_question,
        _last_system_payload,
        _persist_turn_findings,
        _person_context,
        _snapshot_payload,
        add_turn,
        persist_map_version,
        rebuild_case,
        snapshot_from_case,
    )
    from app.discovery.snapshot import prior_facts_from_snapshot
    from app.models.enums import DiscoveryCaseStatus

    completed: list[str] = []

    def _stage(name: str) -> None:
        completed.append(name)
        if fail_after == name:
            raise TurnAborted(name)

    _stage("authenticate")
    source_event_id = idempotency_key or str(uuid.uuid4())
    existing = await _existing_turn(db, case.id, idempotency_key)
    _stage("resolve_source_event")
    if existing is not None:
        increment("turn_idempotent_replay")
        return TurnPipelineResult(
            snapshot=snapshot_from_case(case),
            stages=completed,
            reused=True,
            source_event_id=source_event_id,
        )

    turns = list((await db.execute(select(DiscoveryTurn).where(DiscoveryTurn.case_id == case.id))).scalars())
    findings = list((await db.execute(select(DiscoveryFinding).where(DiscoveryFinding.case_id == case.id))).scalars())
    asked = [turn.question_code for turn in turns if turn.role == DiscoveryTurnRole.SYSTEM and turn.question_code]
    answered = {item.name for item in findings if item.kind == DiscoveryFindingKind.ASSESSMENT and getattr(item, "active", True)}
    prior = facts_from_findings([item for item in findings if getattr(item, "active", True)])
    if getattr(case, "safety_json", None):
        try:
            held = json.loads(case.safety_json)
            if isinstance(held, dict) and held.get("state"):
                prior["safety_state"] = str(held["state"])
        except json.JSONDecodeError:
            pass
    snap_payload = await _snapshot_payload(db, case.patient_id) if case.patient_id else None
    if snap_payload:
        prior = {**prior_facts_from_snapshot(snap_payload), **prior}
    last_visit = None
    if snap_payload:
        from app.discovery.context import last_visit_from_snapshot

        last_visit = last_visit_from_snapshot(snap_payload)
    _stage("load_canonical")

    original, normalized = normalize_input(text)
    _stage("normalize_input")
    if not normalized:
        raise ValueError("empty turn")

    prior_safety = findings_from_fact_map(prior)
    safety_findings = extract_safety_findings(normalized, prior_safety)
    safety = assess_safety(safety_findings, asked=set(asked), prior_state=prior.get("safety_state"), new_text=normalized)
    _stage("safety_screen")

    intents = classify_intent(normalized)
    _stage("classify_intent")

    payload = _last_system_payload(turns)
    current_closes = _closes_for_question((payload.get("action") or {}).get("question_id"))
    person = await _person_context(db, case, prior_facts=prior, last_visit=last_visit, snapshot_payload=snap_payload)
    from app.discovery.evidence_graph import load_open_gaps

    persisted_gaps = await load_open_gaps(db, case.id)
    result = await DiscoveryGuide().process_turn(
        normalized,
        prior_facts=prior,
        asked=asked,
        answered=answered,
        current_closes=current_closes,
        concern=case.presenting_concern or original,
        audience=audience,
        turn_count=len(turns),
        recent_turns=[turn.text for turn in sorted(turns, key=lambda item: item.created_at)][-12:],
        problem=case.problem_representation,
        on_phase=on_phase,
        last_visit=last_visit,
        person=person,
        persisted_gaps=persisted_gaps or None,
        control_state=_control_from_case(case),
    )
    _stage("extract_facts")
    _stage("detect_conflicts")
    _stage("propose_mutations")

    from app.discovery.coverage_catalog import concepts_for_branch, test_code_for_finding

    resolved = []
    mentioned_tests: list[str] = []
    for item in result.new_findings:
        match = resolve_test(item.name)
        resolved.append(match)
        coded = test_code_for_finding(item.name)
        if coded:
            mentioned_tests.append(coded)
        elif match.match is not None:
            mentioned_tests.append(match.match.code)
    _stage("resolve_tests")

    hypo_codes = []
    for item in result.hypotheses or []:
        code = getattr(item, "code", None) or str(item)
        hypo_codes.append(code)
        hypo_codes.extend(concepts_for_branch(code))
        branch = getattr(item, "branch", None)
        if branch:
            hypo_codes.extend(concepts_for_branch(branch))
    branch_codes = list(dict.fromkeys(str(code) for code in hypo_codes if code))[:12]
    coverage_notes = []
    for test_code in dict.fromkeys(mentioned_tests):
        for concept in branch_codes:
            coverage_notes.append(assess_coverage(test_code, concept))
    _stage("assess_coverage")

    first_test = mentioned_tests[0] if mentioned_tests else None
    interpreted = (
        interpret_workup(raw_label=first_test, branch_codes=branch_codes) if first_test and branch_codes else None
    )
    _stage("interpret_evidence")

    lifecycle = propose_transition(
        BranchLifecycleStatus.NOT_EVALUATED,
        BranchLifecycleStatus.CLOSED,
        coverage=coverage_notes[0].relation if coverage_notes else CoverageRelation.UNKNOWN,
        relationship=None,
    )
    _stage("apply_lifecycle")
    _stage("generate_candidates")
    _stage("rank_actions")

    check = validate_scientific_output(
        [
            ScientificItem(
                id="turn-message",
                version="1",
                item_type=ScientificItemType.SYSTEM_INFERENCE,
                statement=result.message,
                provenance=["turn-engine-v1"],
            )
        ]
    )
    if not check.accepted:
        result.message = "I updated the Case. I will not write a diagnosis."
        increment("scientific_output_blocked")
    _stage("validate_output")

    await _attach_literature(case, normalized, result)
    user_turn = await add_turn(
        db,
        case,
        role=DiscoveryTurnRole.USER,
        text=original,
        kind="concern" if opening else "turn",
        intent=",".join(result.intents),
        stage=result.stage,
        payload=json.dumps({"normalized": normalized, "stages": completed, "idempotency_key": source_event_id}),
    )
    user_turn.idempotency_key = source_event_id
    await _persist_turn_findings(db, case.id, result.new_findings, source_event_id=str(user_turn.id))
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
        payload=json.dumps(
            {
                **result.as_dict(),
                "pipeline": completed + ["persist", "render_response", "emit_metrics"],
                "lifecycle": lifecycle.reason,
                "resolved": [item.status.value for item in resolved],
                "interpreted": bool(interpreted and interpreted.edges),
                "safety_screen": safety.state,
                "intents": list(intents),
            }
        ),
    )
    case.stage = result.stage
    case.problem_representation = result.problem_representation
    case.safety_json = json.dumps(result.safety or {})
    if result.control is not None:
        case.control_json = json.dumps(result.control)
    if result.safety_status == "S4":
        case.status = DiscoveryCaseStatus.PAUSED
    await db.flush()
    await persist_map_version(db, case, snapshot)
    _stage("persist")
    _stage("render_response")
    increment("turn_pipeline_completed")
    _stage("emit_metrics")
    return TurnPipelineResult(
        snapshot=snapshot,
        stages=completed,
        source_event_id=source_event_id,
        safety_state=result.safety_status,
    )
