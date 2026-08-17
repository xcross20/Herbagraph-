"""DI-01, DI-05, DI-10, ADR-MVP-001. Current apply_snapshot is expected to fail these."""

import uuid

import pytest
from sqlalchemy import select

from app.discovery.engine import FindingDraft
from app.discovery.service import apply_snapshot, rebuild_case
from app.models.discovery import DiscoveryCase, DiscoveryFinding
from app.models.enums import DiscoveryCaseStatus, DiscoveryFindingKind
from app.models.user import User


async def _case(db_session) -> DiscoveryCase:
    user = User(email=f"mvp-{uuid.uuid4().hex[:10]}@example.com", hashed_password="x")
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
async def test_finding_identity_survives_rebuild(db_session):
    """DI-01 / ADR-MVP-001: rebuild is a projection and must not replace finding identity."""
    case = await _case(db_session)
    row = DiscoveryFinding(
        case_id=case.id,
        kind=DiscoveryFindingKind.SYMPTOM,
        name="burning sensation",
        value="reported",
        source="user",
    )
    db_session.add(row)
    await db_session.flush()
    original_id = row.id
    await rebuild_case(db_session, case)
    held = await db_session.get(DiscoveryFinding, original_id)
    assert held is not None
    assert held.name == "burning sensation"
    assert held.value == "reported"


@pytest.mark.asyncio
async def test_projection_must_not_use_deleted_history(db_session):
    """DI-10: historical rows remain queryable after a later snapshot rebuild."""
    from app.discovery.engine import CaseSnapshot

    case = await _case(db_session)
    first = DiscoveryFinding(
        case_id=case.id,
        kind=DiscoveryFindingKind.CONTEXT,
        name="onset",
        value="after surgery",
        source="user",
    )
    db_session.add(first)
    await db_session.flush()
    first_id = first.id
    snapshot = CaseSnapshot(
        presenting_concern=case.presenting_concern,
        findings=[
            FindingDraft(
                kind="context",
                name="onset",
                value="before surgery",
                status=None,
                branch=None,
                source="user",
            )
        ],
        hypotheses=[],
        branch_coverage=[],
        investigation_coverage=0.0,
    )
    await apply_snapshot(db_session, case, snapshot)
    await db_session.flush()
    original = await db_session.get(DiscoveryFinding, first_id)
    assert original is not None
    assert original.value == "after surgery"


@pytest.mark.asyncio
async def test_second_rebuild_is_not_a_new_truth(db_session):
    """DI-05: repeating rebuild does not create a second semantic finding."""
    case = await _case(db_session)
    db_session.add(
        DiscoveryFinding(
            case_id=case.id,
            kind=DiscoveryFindingKind.SYMPTOM,
            name="burning sensation",
            value="reported",
            source="user",
        )
    )
    await db_session.flush()
    await rebuild_case(db_session, case)
    await rebuild_case(db_session, case)
    rows = list(
        (
            await db_session.execute(
                select(DiscoveryFinding).where(
                    DiscoveryFinding.case_id == case.id,
                    DiscoveryFinding.name == "burning sensation",
                    DiscoveryFinding.value == "reported",
                )
            )
        ).scalars()
    )
    assert len(rows) == 1
