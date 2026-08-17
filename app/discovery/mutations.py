"""Idempotent finding apply. Projection must not delete canonical history."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.discovery.coverage_catalog import normalize_label
from app.discovery.identity import finding_identity_key, finding_source_event_id
from app.models.discovery import DiscoveryFinding
from app.models.enums import DiscoveryFindingKind


async def apply_finding_drafts(db: AsyncSession, case_id, drafts) -> None:
    rows = list(
        (
            await db.execute(select(DiscoveryFinding).where(DiscoveryFinding.case_id == case_id))
        ).scalars()
    )
    by_identity = {row.identity_key: row for row in rows if row.identity_key}
    active_by_name: dict[str, DiscoveryFinding] = {}
    for row in rows:
        if getattr(row, "active", True):
            active_by_name[normalize_label(row.name)] = row

    for item in drafts:
        source_event_id = finding_source_event_id(
            source=item.source or "user",
            name=item.name,
            value=item.value,
        )
        identity_key = finding_identity_key(
            case_id=case_id,
            name=item.name,
            value=item.value,
            source_event_id=source_event_id,
        )
        existing = by_identity.get(identity_key)
        if existing is None:
            existing = next(
                (
                    row
                    for row in rows
                    if normalize_label(row.name) == normalize_label(item.name)
                    and (row.value or "") == (item.value or "")
                ),
                None,
            )
        if existing is not None:
            if not existing.identity_key:
                existing.identity_key = identity_key
                existing.source_event_id = source_event_id
                if getattr(existing, "active", None) is None:
                    existing.active = True
            continue

        current = active_by_name.get(normalize_label(item.name))
        predecessor_id = None
        if current is not None and (current.value or "") != (item.value or ""):
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
        db.add(row)
        rows.append(row)
        by_identity[identity_key] = row
        active_by_name[normalize_label(item.name)] = row
