"""PR-49: ranker uses persisted gaps and keeps safety/commerce constraints."""

from __future__ import annotations

import pytest

from app.discovery.ranker import RANKER_VERSION, rank_next_actions


def test_safety_override_outranks_all_gaps():
    ranked = rank_next_actions(
        gaps=[{"code": "x", "label": "Ask about laterality", "information_value": 0.99, "coverage_gain": 0.99}],
        safety_level="S3",
    )
    assert ranked[0].action_type == "professional_review"
    assert ranked[0].score == 1.0


def test_commerce_boosted_gap_is_filtered():
    ranked = rank_next_actions(
        gaps=[
            {
                "code": "gold",
                "label": "Buy a Gold Label panel",
                "information_value": 0.99,
                "coverage_gain": 0.99,
                "cost": 0.0,
                "commerce_boosted": True,
            },
            {
                "code": "laterality",
                "label": "Clarify laterality",
                "information_value": 0.6,
                "coverage_gain": 0.6,
            },
        ]
    )
    assert ranked[0].gap_code == "laterality"
    assert all(item.gap_code != "gold" or item.rejected_reason for item in ranked)


def test_no_candidate_when_all_filtered():
    ranked = rank_next_actions(
        gaps=[
            {"code": "done", "label": "Already asked", "redundancy": 1.0},
            {"code": "na", "label": "Non-addressing", "non_addressing": True},
        ]
    )
    assert ranked[0].action_type == "no_candidate"


def test_higher_cost_moves_rank_down():
    cheap = {"code": "ask", "label": "Ask", "information_value": 0.7, "coverage_gain": 0.7, "cost": 0.1, "burden": 0.1}
    costly = {"code": "scan", "label": "Scan", "information_value": 0.7, "coverage_gain": 0.7, "cost": 0.9, "burden": 0.9}
    ranked = rank_next_actions(gaps=[costly, cheap])
    assert ranked[0].gap_code == "ask"
    assert ranked[0].alternatives
    assert ranked[0].version == RANKER_VERSION


def test_ranker_does_not_invent_when_empty():
    ranked = rank_next_actions(gaps=[])
    assert ranked[0].action_type == "no_candidate"


@pytest.mark.asyncio
async def test_persisted_gaps_are_ranked_and_learning_does_not_change_rules(db_session):
    import uuid

    from app.discovery.evidence_graph import persist_open_gaps
    from app.discovery.ranker_learning import record_ranker_decision
    from app.models.discovery import DiscoveryCase, DiscoveryHypothesis
    from app.models.enums import DiscoveryCaseStatus, DiscoveryHypothesisStatus
    from app.models.user import User

    user = User(email=f"ranker-{uuid.uuid4().hex[:8]}@example.com", hashed_password="x")
    db_session.add(user)
    await db_session.flush()
    case = DiscoveryCase(
        user_id=user.id,
        presenting_concern="For six months my feet have burned at night.",
        status=DiscoveryCaseStatus.OPEN,
    )
    db_session.add(case)
    await db_session.flush()
    db_session.add(
        DiscoveryHypothesis(
            case_id=case.id,
            code="small_fiber_dysfunction",
            label="Small-fiber investigation",
            branch="peripheral_nerve",
            status=DiscoveryHypothesisStatus.OPEN,
            investigation_relevance=0.7,
            diagnostic_certainty=0.0,
            investigation_coverage=0.2,
        )
    )
    await db_session.flush()
    rows = await persist_open_gaps(db_session, case_id=case.id)
    assert rows
    codes = {item.code for item in rows}
    assert "small_fiber_density" in codes
    event = await record_ranker_decision(
        db_session,
        case_id=case.id,
        decision="deferred",
        gap_code="small_fiber_density",
        source_event_id="ranker-defer-1",
    )
    assert event.kind == "ranker_learning"
    assert "false" in (event.payload or "").lower()
    again = await persist_open_gaps(db_session, case_id=case.id)
    assert {item.code for item in again} == codes


def test_completed_workup_is_not_re_ranked():
    ranked = rank_next_actions(
        gaps=[
            {"code": "emg", "label": "Repeat EMG", "already_completed": True, "information_value": 0.9},
            {"code": "temp", "label": "Ask temperature", "information_value": 0.5},
        ]
    )
    assert ranked[0].gap_code == "temp"
