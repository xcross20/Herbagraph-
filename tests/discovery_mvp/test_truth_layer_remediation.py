"""Issue #37 hostile traces for the merged truth layer."""

from __future__ import annotations

import asyncio
import os
import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import attributes

from app.database import Base
from app.discovery.coverage_governor import assess_coverage
from app.discovery.engine import CaseSnapshot, FindingDraft
from app.discovery.evidence_interpreter import interpret_workup
from app.discovery.identity import finding_identity_key
from app.discovery.map import build_map_payload
from app.discovery.mutations import apply_finding_drafts
from app.discovery.service import apply_snapshot, case_to_read, snapshot_to_read
from app.models.discovery import DiscoveryCase, DiscoveryFinding, DiscoveryEvidenceGap
from app.models.enums import CoverageRelation, DiscoveryCaseStatus, DiscoveryFindingKind
from app.models.user import User


async def _case(db_session) -> DiscoveryCase:
    user = User(email=f"remed-{uuid.uuid4().hex[:10]}@example.com", hashed_password="x")
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


@pytest.mark.asyncio
async def test_all_inactive_persisted_findings_do_not_resurface_from_snapshot(db_session):
    case = await _case(db_session)
    inactive = DiscoveryFinding(
        case_id=case.id,
        kind=DiscoveryFindingKind.CONTEXT,
        name="onset",
        value="after surgery",
        source="user",
        active=False,
    )
    db_session.add(inactive)
    await db_session.flush()
    attributes.set_committed_value(case, "findings", [inactive])
    snapshot = _snapshot(case, "after surgery")
    read = snapshot_to_read(case, snapshot)
    assert read.findings == []
    payload = build_map_payload(
        snapshot=snapshot,
        facts={"onset": "after surgery"},
        unknowns=[],
        findings=[inactive],
    )
    blob = str(payload).lower()
    assert "after surgery" not in blob
    api = await case_to_read(db_session, case)
    assert all(item.value != "after surgery" for item in api.findings)


@pytest.mark.asyncio
async def test_correction_a_to_b_to_a_is_append_only_after_replay_and_restart(db_session):
    case = await _case(db_session)
    await apply_snapshot(db_session, case, _snapshot(case, "after surgery"), source_event_id="evt-a")
    await db_session.flush()
    await apply_snapshot(db_session, case, _snapshot(case, "before surgery"), source_event_id="evt-b")
    await db_session.flush()
    await apply_snapshot(db_session, case, _snapshot(case, "after surgery"), source_event_id="evt-a2")
    await db_session.flush()
    await apply_snapshot(db_session, case, _snapshot(case, "after surgery"), source_event_id="evt-a2")
    await db_session.flush()

    rows = list(
        (
            await db_session.execute(select(DiscoveryFinding).where(DiscoveryFinding.case_id == case.id))
        ).scalars()
    )
    assert len(rows) == 3
    actives = [row for row in rows if row.active]
    assert len(actives) == 1
    assert actives[0].value == "after surgery"
    first_a = next(row for row in rows if row.source_event_id == "evt-a")
    assert first_a.active is False
    assert actives[0].id != first_a.id
    assert actives[0].supersedes_finding_id is not None

    case_id = case.id
    await db_session.commit()
    db_session.expire_all()
    restarted = list(
        (
            await db_session.execute(select(DiscoveryFinding).where(DiscoveryFinding.case_id == case_id))
        ).scalars()
    )
    restarted_active = [row for row in restarted if row.active]
    assert [row.value for row in restarted_active] == ["after surgery"]
    held = await db_session.get(DiscoveryCase, case_id)
    attributes.set_committed_value(held, "findings", restarted)
    read = snapshot_to_read(held, _snapshot(held, "after surgery"))
    assert [item.value for item in read.findings] == ["after surgery"]


def test_absent_coverage_is_unknown_explicit_not_applicable_stays_distinct():
    unknown = assess_coverage("emg_ncs", "biliary_stones")
    explicit = assess_coverage("cbc", "small_fiber_density")
    assert unknown.relation is CoverageRelation.UNKNOWN
    assert explicit.relation is CoverageRelation.NOT_APPLICABLE
    interpreted = interpret_workup(
        raw_label="EMG",
        branch_codes=["biliary_stones"],
        result_state="negative",
    )
    assert interpreted.edges == []
    assert any("unknown" in item for item in interpreted.discarded)


def _postgres_url() -> str | None:
    for key in ("HERBAGRAPH_TEST_POSTGRES", "DATABASE_URL"):
        value = os.environ.get(key) or ""
        if "postgres" in value.lower():
            return value.replace("postgresql://", "postgresql+asyncpg://") if value.startswith("postgresql://") else value
    return None


@pytest.mark.asyncio
@pytest.mark.requires_postgres
async def test_two_postgres_sessions_converge_on_one_semantic_finding():
    url = _postgres_url()
    if url is None:
        if os.environ.get("HERBAGRAPH_REQUIRE_POSTGRES") == "1":
            pytest.fail("PostgreSQL URL required; skip is not allowed on a truth-layer PR")
        pytest.skip("PostgreSQL URL not provided; two-session race requires a real engine")

    engine = create_async_engine(url, future=True)
    schema = f"truth_{uuid.uuid4().hex[:10]}"
    try:
        async with engine.begin() as conn:
            await conn.execute(text(f"CREATE SCHEMA {schema}"))
            await conn.execute(text(f"SET search_path TO {schema}"))
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)

        async def _prepare():
            async with factory() as session:
                await session.execute(text(f"SET search_path TO {schema}"))
                user = User(email=f"pg-{uuid.uuid4().hex[:8]}@example.com", hashed_password="x")
                session.add(user)
                await session.flush()
                case = DiscoveryCase(
                    user_id=user.id,
                    presenting_concern="burning feet",
                    status=DiscoveryCaseStatus.OPEN,
                )
                session.add(case)
                await session.commit()
                return case.id

        case_id = await _prepare()
        draft = FindingDraft(
            kind="context",
            name="onset",
            value="night",
            status=None,
            branch=None,
            source="user",
        )

        barrier = asyncio.Barrier(2)
        outcomes: list[str] = []

        async def _apply():
            async with factory() as session:
                await session.execute(text(f"SET search_path TO {schema}"))

                async def _after_read():
                    await barrier.wait()

                try:
                    await apply_finding_drafts(
                        session,
                        case_id,
                        [draft],
                        source_event_id="same-turn",
                        after_read=_after_read,
                    )
                    await session.commit()
                    outcomes.append("committed")
                except Exception as exc:  # noqa: BLE001 - record defined loser recovery
                    await session.rollback()
                    existing = (
                        await session.execute(
                            select(DiscoveryFinding).where(DiscoveryFinding.case_id == case_id)
                        )
                    ).scalars().all()
                    if existing:
                        outcomes.append("recovered")
                        return
                    outcomes.append(f"failed:{type(exc).__name__}")
                    raise

        results = await asyncio.gather(_apply(), _apply(), return_exceptions=True)
        assert all(item is None or isinstance(item, Exception) for item in results)
        assert all(item in {"committed", "recovered"} for item in outcomes)
        assert "committed" in outcomes
        assert len(outcomes) == 2
        if isinstance(results[0], Exception) and isinstance(results[1], Exception):
            raise AssertionError(f"both workers failed: {results}")

        async with factory() as session:
            await session.execute(text(f"SET search_path TO {schema}"))
            rows = list(
                (
                    await session.execute(select(DiscoveryFinding).where(DiscoveryFinding.case_id == case_id))
                ).scalars()
            )
        assert len(rows) == 1
        assert rows[0].value == "night"
        expected = finding_identity_key(
            case_id=case_id,
            name="onset",
            value="night",
            source_event_id="same-turn",
        )
        assert rows[0].identity_key == expected
    finally:
        async with engine.begin() as conn:
            await conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        await engine.dispose()


@pytest.mark.asyncio
async def test_dark_launch_off_does_not_write_findings(db_session, monkeypatch):
    from app.config import get_settings
    from app.discovery.telemetry import snapshot

    monkeypatch.setenv("DISCOVERY_TRUTH_LAYER_AUTHORITATIVE", "false")
    get_settings.cache_clear()
    try:
        case = await _case(db_session)
        before = snapshot().get("dark_launch_write_suppressed", 0)
        await apply_snapshot(db_session, case, _snapshot(case, "after surgery"), source_event_id="dark-off")
        await db_session.flush()
        rows = list(
            (
                await db_session.execute(select(DiscoveryFinding).where(DiscoveryFinding.case_id == case.id))
            ).scalars()
        )
        assert rows == []
        assert snapshot().get("dark_launch_write_suppressed", 0) >= before + 1
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_note_and_removal_use_mutation_seam(db_session):
    from app.discovery.service import record_user_note, remove_named_finding

    case = await _case(db_session)
    await record_user_note(db_session, case, "Patient clarified the burning is worse at night.")
    await db_session.flush()
    rows = list(
        (
            await db_session.execute(select(DiscoveryFinding).where(DiscoveryFinding.case_id == case.id))
        ).scalars()
    )
    notes = [row for row in rows if row.name == "Additional note"]
    assert len(notes) == 1
    assert notes[0].identity_key
    await remove_named_finding(db_session, case, "Additional note")
    await db_session.flush()
    held = list(
        (
            await db_session.execute(select(DiscoveryFinding).where(DiscoveryFinding.case_id == case.id))
        ).scalars()
    )
    notes = [row for row in held if row.name == "Additional note"]
    assert notes
    assert all(row.active is False for row in notes)


def test_inactive_exposed_projection_is_reachable():
    from types import SimpleNamespace

    from app.discovery.tripwires import evaluate_finding_projection

    inactive = SimpleNamespace(
        id="inactive-1",
        name="onset",
        value="after surgery",
        active=False,
        supersedes_finding_id=None,
    )
    active = SimpleNamespace(
        id="active-1",
        name="onset",
        value="before surgery",
        active=True,
        supersedes_finding_id="inactive-1",
    )
    exposed = [inactive]
    violations = evaluate_finding_projection([inactive, active], exposed=exposed)
    assert "inactive_finding_exposed_as_active" in violations
    clean = evaluate_finding_projection([inactive, active], exposed=[active])
    assert "inactive_finding_exposed_as_active" not in clean


def test_alembic_and_orm_agree_on_self_fk_and_active_gap_index():
    fks = DiscoveryFinding.__table__.c.supersedes_finding_id.foreign_keys
    assert any(fk.column.table.name == "discovery_findings" for fk in fks)
    gap_indexes = {index.name: index for index in DiscoveryEvidenceGap.__table__.indexes}
    assert "uq_discovery_gaps_active_code" in gap_indexes
    assert gap_indexes["uq_discovery_gaps_active_code"].unique is True
    from pathlib import Path

    revisions = "\n".join(path.read_text() for path in Path("alembic/versions").glob("*.py"))
    assert "fk_discovery_findings_supersedes" in revisions
    assert "uq_discovery_gaps_active_code" in revisions
