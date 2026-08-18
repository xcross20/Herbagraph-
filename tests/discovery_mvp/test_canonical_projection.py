"""DI-01, DI-05, DI-09, DI-10, ADR-MVP-001, ADR-MVP-004."""

from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import select

from app.discovery.engine import CaseSnapshot, FindingDraft
from app.discovery.map import build_map_payload
from app.discovery.service import apply_snapshot, case_to_read, rebuild_case, snapshot_to_read
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


@pytest.mark.asyncio
async def test_correction_preserves_original_history(db_session):
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
    assert original.active is False


@pytest.mark.asyncio
async def test_correction_links_replacement_and_excludes_inactive_history_from_all_active_projections(
    db_session,
):
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
    rows = list(
        (
            await db_session.execute(
                select(DiscoveryFinding).where(DiscoveryFinding.case_id == case.id)
            )
        ).scalars()
    )
    replacement = next((row for row in rows if row.id != first_id and row.value == "before surgery"), None)
    assert original is not None
    assert original.active is False
    assert replacement is not None
    assert replacement.supersedes_finding_id == first_id

    from sqlalchemy.orm import attributes

    attributes.set_committed_value(case, "findings", rows)
    read = snapshot_to_read(case, snapshot)
    payload = build_map_payload(
        snapshot=snapshot,
        facts={"onset": "before surgery"},
        unknowns=[],
        findings=read.findings,
        canonical_findings=rows,
    )
    assert all(item.value != "after surgery" for item in read.findings)
    assert "after surgery" not in json.dumps([item.model_dump() for item in read.findings], default=str).lower()
    for branch in payload.get("branches") or []:
        assert "after surgery" not in json.dumps(branch, default=str).lower()
    history = payload.get("finding_history") or []
    assert any(item.get("value") == "after surgery" and item.get("active") is False for item in history)

    api_read = await case_to_read(db_session, case)
    assert all(item.value != "after surgery" for item in api_read.findings)


@pytest.mark.asyncio
async def test_second_rebuild_is_not_a_new_truth(db_session):
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
