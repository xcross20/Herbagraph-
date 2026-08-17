"""Hostile failure injection. Users must see partial/failed, not plausible success."""

from __future__ import annotations

import pytest

from app.discovery.evidence_mapping import coverage_to_evidence_relationship
from app.discovery.lifecycle import propose_transition
from app.discovery.monitoring import record_monitoring_event
from app.discovery.scientific_output import ScientificItem, validate_scientific_output
from app.models.enums import (
    BranchLifecycleStatus,
    CoverageRelation,
    EvidenceRelationship,
    MonitoringOutcomeKind,
    ScientificItemType,
)


def test_invalid_enum_does_not_become_evidence():
    assert coverage_to_evidence_relationship("not_a_real_coverage") is None
    assert coverage_to_evidence_relationship("supports") is None


def test_malformed_coverage_never_closes_a_branch():
    decision = propose_transition(
        BranchLifecycleStatus.NOT_EVALUATED,
        BranchLifecycleStatus.CLOSED,
        coverage=CoverageRelation.UNKNOWN,
        relationship=EvidenceRelationship.INCONCLUSIVE,
    )
    assert decision.accepted is False
    assert decision.resolved_at is None


def test_partial_scientific_output_is_rejected_not_completed():
    result = validate_scientific_output(
        [
            ScientificItem(
                id="x",
                version="1",
                item_type=ScientificItemType.SYSTEM_INFERENCE,
                statement="This confirms the diagnosis.",
                provenance=[],
            )
        ]
    )
    assert result.accepted is False
    assert result.violations


@pytest.mark.asyncio
async def test_stale_retry_and_causal_language_are_explicit_failures(db_session):
    from app.models.discovery import DiscoveryCase
    from app.models.enums import DiscoveryCaseStatus
    from app.models.user import User
    import uuid

    user = User(email=f"inj-{uuid.uuid4().hex[:8]}@example.com", hashed_password="x")
    db_session.add(user)
    await db_session.flush()
    case = DiscoveryCase(
        user_id=user.id,
        presenting_concern="burning feet",
        status=DiscoveryCaseStatus.OPEN,
    )
    db_session.add(case)
    await db_session.flush()
    with pytest.raises(ValueError):
        await record_monitoring_event(
            db_session,
            case_id=case.id,
            target="burning sensation",
            observation_time="2026-08-17",
            outcome_kind=MonitoringOutcomeKind.IMPROVED,
            source_event_id="retry-1",
            notes="the supplement caused this",
        )


def test_llm_timeout_and_malformed_json_are_not_success():
    from app.discovery.failure_modes import commit_without_response, document_parse_incomplete, llm_timeout, recover_json

    assert llm_timeout().status == "failed"
    assert recover_json("{").status in {"failed", "partial"}
    assert recover_json('{"ok": true').status == "partial"
    assert recover_json('{"ok": true}').status == "succeeded"
    assert document_parse_incomplete(parsed_rows=1, expected_rows=4).status == "partial"
    assert commit_without_response().status == "partial"
    assert commit_without_response().detail == "committed_response_unsent"


@pytest.mark.asyncio
async def test_duplicate_event_and_restart_during_correction_converge(db_session):
    import uuid

    from app.discovery.engine import CaseSnapshot, FindingDraft
    from app.discovery.service import apply_snapshot
    from app.models.discovery import DiscoveryCase, DiscoveryFinding
    from app.models.enums import DiscoveryCaseStatus
    from app.models.user import User
    from sqlalchemy import select

    user = User(email=f"dup-{uuid.uuid4().hex[:8]}@example.com", hashed_password="x")
    db_session.add(user)
    await db_session.flush()
    case = DiscoveryCase(
        user_id=user.id,
        presenting_concern="burning feet",
        status=DiscoveryCaseStatus.OPEN,
    )
    db_session.add(case)
    await db_session.flush()

    def snap(value: str) -> CaseSnapshot:
        return CaseSnapshot(
            presenting_concern=case.presenting_concern,
            findings=[
                FindingDraft(kind="context", name="onset", value=value, status=None, branch=None, source="user")
            ],
            hypotheses=[],
            branch_coverage=[],
            investigation_coverage=0.0,
        )

    case_id = case.id
    await apply_snapshot(db_session, case, snap("after surgery"), source_event_id="evt-a")
    await apply_snapshot(db_session, case, snap("before surgery"), source_event_id="evt-b")
    await db_session.flush()
    await db_session.commit()
    db_session.expire_all()
    held = await db_session.get(DiscoveryCase, case_id)
    await apply_snapshot(db_session, held, snap("before surgery"), source_event_id="evt-b")
    await db_session.flush()
    rows = list(
        (await db_session.execute(select(DiscoveryFinding).where(DiscoveryFinding.case_id == case_id))).scalars()
    )
    actives = [row for row in rows if row.active]
    assert len(actives) == 1
    assert actives[0].value == "before surgery"
