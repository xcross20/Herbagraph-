"""DI-01, DI-05, partial DI-09, ADR-MVP-001, ADR-MVP-004.

These tests reproduce the live defect on current main: `apply_snapshot`
deletes findings and inserts a new snapshot. They do not reproduce V2
Issues 4–7 (inverted FKs, inactive leak through a graph persist path).
Those modules are absent here; see the V2 forensic SHA in `red.py`.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.discovery.engine import CaseSnapshot, FindingDraft
from app.discovery.service import apply_snapshot, rebuild_case
from app.models.discovery import DiscoveryCase, DiscoveryFinding
from app.models.enums import DiscoveryCaseStatus, DiscoveryFindingKind
from app.models.user import User
from tests.discovery_mvp.red import SCAFFOLDED, reproduced_on_main


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


def _onset_snapshot(case: DiscoveryCase, value: str) -> CaseSnapshot:
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


@reproduced_on_main(
    invariant="DI-01",
    defect="apply_snapshot deletes the original finding row",
)
@pytest.mark.asyncio
async def test_finding_identity_survives_rebuild(db_session):
    """Rebuild is a projection and must not replace finding identity."""
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
    original_created = row.created_at
    await rebuild_case(db_session, case)
    held = await db_session.get(DiscoveryFinding, original_id)
    assert held is not None
    assert held.id == original_id
    assert held.name == "burning sensation"
    assert held.value == "reported"
    assert held.created_at == original_created


@reproduced_on_main(
    invariant="DI-09 (history preservation only)",
    defect="apply_snapshot destroys the original row instead of preserving correction history",
)
@pytest.mark.asyncio
async def test_correction_preserves_original_history(db_session):
    """A correction must not delete the original historical finding.

    This reproduces only the first live failure. Link direction and active-only
    projection are separate scaffolded claims because the current model has no
    correction or active-history fields and execution cannot reach them.
    """
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
    snapshot = _onset_snapshot(case, "before surgery")
    await apply_snapshot(db_session, case, snapshot)
    await db_session.flush()

    original = await db_session.get(DiscoveryFinding, first_id)
    assert original is not None
    assert original.value == "after surgery"


@pytest.mark.skip(
    reason=(
        f"{SCAFFOLDED}: correction linkage and inactive-history fields are absent on "
        "integration/agent; PR-D must prove predecessor direction and active-only "
        "prompt/map/report projection at persistence and API boundaries"
    )
)
def test_correction_links_replacement_and_excludes_inactive_history_from_all_active_projections():
    """DI-09/DI-10 and ISS-04/05/06 contract; not evidence until PR-D."""
    raise AssertionError("unreachable until the PR-D correction path exists")


@reproduced_on_main(
    invariant="DI-05",
    defect="rebuild deletes and inserts; row count 1 can hide identity churn",
)
@pytest.mark.asyncio
async def test_second_rebuild_is_not_a_new_truth(db_session):
    """Hostile trace: rebuild 1 deletes A/inserts B; rebuild 2 deletes B/inserts C.

    Final count 1 is not enough. IDs, semantic identity, and audit timestamps
    must be stable. Projection must not mutate canonical rows.
    """
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
    original_created = row.created_at
    original_source = row.source

    await rebuild_case(db_session, case)
    await rebuild_case(db_session, case)

    held = await db_session.get(DiscoveryFinding, original_id)
    assert held is not None
    assert held.id == original_id
    assert held.name == "burning sensation"
    assert held.value == "reported"
    assert held.source == original_source
    assert held.created_at == original_created

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
    assert [item.id for item in rows] == [original_id]
