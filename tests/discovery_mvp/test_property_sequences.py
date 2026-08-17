"""Generated action sequences. Invariants must hold after every step."""

from __future__ import annotations

import random
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import attributes

from app.discovery.coverage_governor import assess_coverage
from app.discovery.engine import CaseSnapshot, FindingDraft
from app.discovery.evidence_interpreter import interpret_workup
from app.discovery.lifecycle import propose_transition
from app.discovery.service import apply_snapshot, snapshot_to_read
from app.discovery.tripwires import evaluate_finding_projection
from app.models.discovery import DiscoveryCase, DiscoveryFinding
from app.models.enums import BranchLifecycleStatus, CoverageRelation, DiscoveryCaseStatus
from app.models.user import User

ACTIONS = (
    "create",
    "correct",
    "correct_again",
    "replay",
    "rebuild",
    "restart",
    "close_attempt",
    "upload_emg",
    "duplicate_upload",
)


def _snapshot(case: DiscoveryCase, value: str) -> CaseSnapshot:
    return CaseSnapshot(
        presenting_concern=case.presenting_concern,
        findings=[
            FindingDraft(
                kind="context",
                name="onset",
                value=value,
                status=None,
                branch=None,
                source="user",
            )
        ],
        hypotheses=[],
        branch_coverage=[],
        investigation_coverage=0.0,
    )


async def _assert_invariants(db_session, case: DiscoveryCase) -> None:
    rows = list(
        (
            await db_session.execute(select(DiscoveryFinding).where(DiscoveryFinding.case_id == case.id))
        ).scalars()
    )
    violations = evaluate_finding_projection(rows)
    assert "multiple_active_semantic_facts" not in violations
    assert "correction_missing_predecessor" not in violations
    attributes.set_committed_value(case, "findings", rows)
    read = snapshot_to_read(case, _snapshot(case, "ignored"))
    active_ids = {row.id for row in rows if row.active}
    assert len(active_ids) <= 1
    for item in read.findings:
        assert any(
            row.active and row.name == item.name and row.value == item.value for row in rows
        )
    ids = {row.id for row in rows}
    assert len(ids) == len(rows)


@pytest.mark.asyncio
@pytest.mark.parametrize("seed", range(48))
async def test_generated_sequences_preserve_truth_invariants(db_session, seed: int):
    rng = random.Random(seed)
    user = User(email=f"prop-{seed}-{uuid.uuid4().hex[:6]}@example.com", hashed_password="x")
    db_session.add(user)
    await db_session.flush()
    case = DiscoveryCase(
        user_id=user.id,
        presenting_concern="For six months my feet have burned at night.",
        status=DiscoveryCaseStatus.OPEN,
    )
    db_session.add(case)
    await db_session.flush()

    values = ["after surgery", "before surgery"]
    current = values[0]
    event = 0
    await apply_snapshot(db_session, case, _snapshot(case, current), source_event_id=f"s{seed}-0")
    await db_session.flush()
    await _assert_invariants(db_session, case)

    for step in range(8):
        action = rng.choice(ACTIONS)
        if action in {"correct", "correct_again"}:
            current = values[1] if current == values[0] else values[0]
            event += 1
            await apply_snapshot(db_session, case, _snapshot(case, current), source_event_id=f"s{seed}-{event}")
        elif action == "replay":
            await apply_snapshot(db_session, case, _snapshot(case, current), source_event_id=f"s{seed}-{event}")
        elif action in {"rebuild", "restart", "create"}:
            await apply_snapshot(db_session, case, _snapshot(case, current), source_event_id=f"s{seed}-{event}")
        elif action == "close_attempt":
            interpreted = interpret_workup(raw_label="EMG", branch_codes=["small_fiber_density"], result_state="negative")
            edge = interpreted.edges[0]
            decision = propose_transition(
                BranchLifecycleStatus.NOT_EVALUATED,
                BranchLifecycleStatus.CLOSED,
                coverage=edge.coverage,
                relationship=edge.relationship,
            )
            assert decision.accepted is False
            assert assess_coverage("emg_ncs", "biliary_stones").relation is CoverageRelation.UNKNOWN
        else:
            interpreted = interpret_workup(raw_label="EMG", branch_codes=["biliary_stones"])
            assert interpreted.edges == []
        await db_session.flush()
        await _assert_invariants(db_session, case)
