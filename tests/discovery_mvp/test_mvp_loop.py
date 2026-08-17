"""PR-E through PR-I: lifecycle, output, ranker, monitoring, gold cases."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.discovery.evidence_interpreter import interpret_workup
from app.discovery.lifecycle import propose_transition
from app.discovery.monitoring import record_monitoring_event
from app.discovery.ranker import rank_next_actions
from app.discovery.scientific_output import ScientificItem, validate_scientific_output
from app.discovery.identity import finding_identity_key, finding_source_event_id
from app.models.discovery import DiscoveryCase, DiscoveryFinding
from app.models.enums import (
    BranchLifecycleStatus,
    CoverageRelation,
    DiscoveryCaseStatus,
    DiscoveryFindingKind,
    EvidenceRelationship,
    MonitoringOutcomeKind,
    ScientificItemType,
)
from app.models.user import User


async def _case(db_session) -> DiscoveryCase:
    user = User(email=f"mvp-loop-{uuid.uuid4().hex[:10]}@example.com", hashed_password="x")
    db_session.add(user)
    await db_session.flush()
    case = DiscoveryCase(
        user_id=user.id,
        presenting_concern="For six months my feet have burned at night.",
        status=DiscoveryCaseStatus.OPEN,
    )
    db_session.add(case)
    await db_session.flush()
    return case


def test_e2e_burning_feet_normal_emg_keeps_small_fiber_open():
    interpreted = interpret_workup(
        raw_label="EMG",
        branch_codes=["small_fiber_density", "large_fiber_function"],
        result_state="negative",
    )
    small = next(edge for edge in interpreted.edges if edge.branch_code == "small_fiber_density")
    assert small.relationship is EvidenceRelationship.DOES_NOT_ADDRESS
    decision = propose_transition(
        BranchLifecycleStatus.NOT_EVALUATED,
        BranchLifecycleStatus.CLOSED,
        coverage=small.coverage,
        relationship=small.relationship,
    )
    assert decision.accepted is False
    assert decision.resolved_at is None


def test_e2e_gallbladder_plus_unrelated_emg_creates_no_biliary_edge():
    interpreted = interpret_workup(
        raw_label="EMG",
        branch_codes=["biliary_stones"],
        result_state="negative",
    )
    assert interpreted.edges == []
    assert any("not_applicable" in item for item in interpreted.discarded)


def test_scientific_output_rejects_diagnosis_and_sourceless_claims():
    bad = ScientificItem(
        id="c1",
        version="1",
        item_type=ScientificItemType.SYSTEM_INFERENCE,
        statement="You have small-fiber neuropathy.",
        provenance=[],
    )
    result = validate_scientific_output([bad], commerce_boosted=True)
    assert result.accepted is False
    assert any("diagnostic_language" in item for item in result.violations)
    assert any("missing_provenance" in item for item in result.violations)
    assert "commerce_cannot_change_scientific_rank" in result.violations


def test_ranker_safety_overrides_and_gap_order():
    safety = rank_next_actions(gaps=[{"code": "ienfd", "label": "IENFD", "branch_code": "small_fiber_density"}], safety_level="S4")
    assert safety[0].action_type == "professional_review"
    ranked = rank_next_actions(
        gaps=[
            {"code": "laterality", "label": "Clarify laterality", "branch_code": "small_fiber_density", "information_value": 0.8},
            {"code": "ienfd", "label": "IENFD biopsy", "branch_code": "small_fiber_density", "information_value": 0.9},
        ]
    )
    assert ranked[0].gap_code == "ienfd"
    assert ranked[0].components["information_value"] == 0.9


@pytest.mark.asyncio
async def test_monitoring_records_no_change_and_rejects_causation(db_session):
    case = await _case(db_session)
    event = await record_monitoring_event(
        db_session,
        case_id=case.id,
        target="burning sensation",
        observation_time="2026-08-17",
        outcome_kind=MonitoringOutcomeKind.NO_CHANGE,
        source_event_id="turn-1",
        exposure="taken",
        adherence="partial",
    )
    assert event.causal_claim is False
    with pytest.raises(ValueError, match="causation"):
        await record_monitoring_event(
            db_session,
            case_id=case.id,
            target="burning sensation",
            observation_time="2026-08-18",
            outcome_kind=MonitoringOutcomeKind.IMPROVED,
            source_event_id="turn-2",
            notes="B12 caused the change",
        )


@pytest.mark.asyncio
async def test_replayed_finding_identity_does_not_duplicate(db_session):
    case = await _case(db_session)
    source = finding_source_event_id(source="user", name="onset", value="night")
    key = finding_identity_key(case_id=case.id, name="onset", value="night", source_event_id=source)
    first = DiscoveryFinding(
        case_id=case.id,
        kind=DiscoveryFindingKind.CONTEXT,
        name="onset",
        value="night",
        source="user",
        active=True,
        source_event_id=source,
        identity_key=key,
    )
    db_session.add(first)
    await db_session.flush()
    db_session.add(
        DiscoveryFinding(
            case_id=case.id,
            kind=DiscoveryFindingKind.CONTEXT,
            name="onset",
            value="night",
            source="user",
            active=True,
            source_event_id=source,
            identity_key=key,
        )
    )
    with pytest.raises(Exception):
        await db_session.flush()
    await db_session.rollback()
    case = await _case(db_session)
    source = finding_source_event_id(source="user", name="onset", value="night")
    key = finding_identity_key(case_id=case.id, name="onset", value="night", source_event_id=source)
    db_session.add(
        DiscoveryFinding(
            case_id=case.id,
            kind=DiscoveryFindingKind.CONTEXT,
            name="onset",
            value="night",
            source="user",
            active=True,
            source_event_id=source,
            identity_key=key,
        )
    )
    await db_session.flush()
    count = list(
        (
            await db_session.execute(
                select(DiscoveryFinding).where(DiscoveryFinding.identity_key == key)
            )
        ).scalars()
    )
    assert len(count) == 1


def test_ienfd_may_close_small_fiber_when_rule_resolves():
    decision = propose_transition(
        BranchLifecycleStatus.EVALUATED_OPEN,
        BranchLifecycleStatus.CLOSED,
        coverage=CoverageRelation.DIRECTLY_ASSESSES,
        relationship=EvidenceRelationship.RESOLVES_GAP,
    )
    assert decision.accepted is True
    assert decision.resolved_at is not None
