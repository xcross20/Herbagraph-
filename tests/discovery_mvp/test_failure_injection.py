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
