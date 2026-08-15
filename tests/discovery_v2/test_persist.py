"""Append-only mutations do not delete history."""

import uuid

import pytest
from sqlalchemy import select

from app.discovery.mutations import FindingMutation, MutationBatch, SupersedeMutation, apply_mutation_batch
from app.models.discovery import DiscoveryCase, DiscoveryFinding
from app.models.enums import DiscoveryCaseStatus, DiscoveryVerificationState
from app.models.user import User


@pytest.mark.asyncio
async def test_correction_keeps_prior_finding_inactive(db_session):
    user = User(email=f"v2-{uuid.uuid4().hex[:8]}@example.com", hashed_password="x")
    db_session.add(user)
    await db_session.flush()
    case = DiscoveryCase(
        user_id=user.id,
        presenting_concern="Pain after surgery",
        status=DiscoveryCaseStatus.OPEN,
    )
    db_session.add(case)
    await db_session.flush()
    first = MutationBatch(add_findings=[FindingMutation(name="onset", value="after surgery", kind="context")])
    await apply_mutation_batch(db_session, case, first)
    second = MutationBatch(
        supersede_findings=[
            SupersedeMutation(
                previous_name="onset",
                previous_value="after surgery",
                name="onset",
                value="two months before surgery",
                reason="user correction",
            )
        ]
    )
    await apply_mutation_batch(db_session, case, second)
    rows = list(
        (await db_session.execute(select(DiscoveryFinding).where(DiscoveryFinding.case_id == case.id))).scalars()
    )
    assert len(rows) >= 2
    inactive = [item for item in rows if item.value == "after surgery"]
    active = [item for item in rows if item.value == "two months before surgery" and item.is_active]
    assert inactive
    assert all(item.is_active is False for item in inactive)
    assert all(item.verification_state == DiscoveryVerificationState.CORRECTED for item in inactive)
    assert active
