"""Atomic 19-step turn pipeline."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.discovery.service import apply_opening_turn, apply_user_turn
from app.discovery.turn_engine import STAGES, TurnAborted, run_turn
from app.models.discovery import DiscoveryCase, DiscoveryFinding, DiscoveryTurn
from app.models.enums import DiscoveryCaseStatus
from app.models.user import User


async def _case(db_session) -> DiscoveryCase:
    user = User(email=f"turn-{uuid.uuid4().hex[:8]}@example.com", hashed_password="x")
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


@pytest.mark.asyncio
async def test_pipeline_records_all_nineteen_stages(db_session):
    case = await _case(db_session)
    result = await run_turn(db_session, case, "The burning is worse at night.")
    assert result.stages == list(STAGES)
    assert result.reused is False


@pytest.mark.asyncio
async def test_failure_before_persist_writes_nothing(db_session):
    case = await _case(db_session)
    with pytest.raises(TurnAborted):
        await run_turn(db_session, case, "The burning is worse at night.", fail_after="validate_output")
    turns = list((await db_session.execute(select(DiscoveryTurn).where(DiscoveryTurn.case_id == case.id))).scalars())
    findings = list(
        (await db_session.execute(select(DiscoveryFinding).where(DiscoveryFinding.case_id == case.id))).scalars()
    )
    assert turns == []
    assert findings == []


@pytest.mark.asyncio
async def test_idempotent_http_key_replays_committed_result(db_session):
    case = await _case(db_session)
    first = await run_turn(db_session, case, "Onset was after surgery.", idempotency_key="evt-1")
    await db_session.flush()
    count = len(
        list((await db_session.execute(select(DiscoveryTurn).where(DiscoveryTurn.case_id == case.id))).scalars())
    )
    second = await run_turn(db_session, case, "Onset was after surgery.", idempotency_key="evt-1")
    assert second.reused is True
    later = list((await db_session.execute(select(DiscoveryTurn).where(DiscoveryTurn.case_id == case.id))).scalars())
    assert len(later) == count
    assert first.source_event_id == "evt-1"


@pytest.mark.asyncio
async def test_safety_remains_after_innocuous_followup(db_session):
    case = await _case(db_session)
    first = await run_turn(db_session, case, "Chest pain and I cannot catch my breath.")
    assert first.safety_state in {"S3", "S4"}
    second = await run_turn(db_session, case, "The weather is nice today.")
    assert second.safety_state in {"S3", "S4", first.safety_state}


@pytest.mark.asyncio
async def test_apply_user_turn_uses_pipeline(db_session):
    case = await _case(db_session)
    snapshot = await apply_user_turn(db_session, case, "The burning is worse at night.")
    assert snapshot.presenting_concern
    opening = await apply_opening_turn(db_session, case, case.presenting_concern)
    assert opening.presenting_concern
