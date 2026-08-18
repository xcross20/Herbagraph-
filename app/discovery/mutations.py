"""Idempotent finding apply. Projection must not delete or resurrect history."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.discovery.coverage_catalog import normalize_label
from app.discovery.identity import finding_identity_key
from app.models.discovery import DiscoveryFinding
from app.models.enums import DiscoveryFindingKind


async def apply_finding_drafts(
    db: AsyncSession,
    case_id,
    drafts,
    *,
    source_event_id: str,
    after_read=None,
) -> None:
    rows = list(
        (
            await db.execute(select(DiscoveryFinding).where(DiscoveryFinding.case_id == case_id))
        ).scalars()
    )
    if after_read is not None:
        await after_read()
    by_identity = {row.identity_key: row for row in rows if row.identity_key}
    active_by_name: dict[str, DiscoveryFinding] = {}
    for row in rows:
        if getattr(row, "active", True):
            active_by_name[normalize_label(row.name)] = row

    for item in drafts:
        identity_key = finding_identity_key(
            case_id=case_id,
            name=item.name,
            value=item.value,
            source_event_id=source_event_id,
        )
        if identity_key in by_identity:
            continue

        name_key = normalize_label(item.name)
        current = active_by_name.get(name_key)
        if current is not None and (current.value or "") == (item.value or ""):
            if not current.identity_key:
                current.identity_key = identity_key
                current.source_event_id = source_event_id
            continue

        predecessor_id = None
        if current is not None:
            current.active = False
            predecessor_id = current.id

        row = DiscoveryFinding(
            case_id=case_id,
            kind=DiscoveryFindingKind(item.kind),
            name=item.name,
            value=item.value,
            status=item.status,
            branch=item.branch,
            source=item.source,
            active=True,
            source_event_id=source_event_id,
            identity_key=identity_key,
            supersedes_finding_id=predecessor_id,
        )
        try:
            async with db.begin_nested():
                db.add(row)
                await db.flush()
        except IntegrityError:
            existing = (
                await db.execute(
                    select(DiscoveryFinding).where(
                        DiscoveryFinding.case_id == case_id,
                        DiscoveryFinding.identity_key == identity_key,
                    )
                )
            ).scalar_one_or_none()
            if existing is None:
                raise
            row = existing
        rows.append(row)
        by_identity[identity_key] = row
        if getattr(row, "active", True):
            active_by_name[name_key] = row
