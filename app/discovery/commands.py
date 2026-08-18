"""Typed mutation commands. The only public write boundary for findings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select

from app.discovery.coverage_catalog import normalize_label
from app.discovery.engine import FindingDraft
from app.discovery.mutations import apply_finding_drafts, inactivate_findings_by_name
from app.models.discovery import DiscoveryFinding

MutationType = Literal["assert", "correct", "inactivate", "verify"]


@dataclass(frozen=True)
class MutationCommand:
    case_id: object
    source_event_id: str
    actor: str
    mutation_type: MutationType
    name: str
    value: str | None
    kind: str
    source: str
    schema_version: str = "mutation-v1"


async def apply_command(db, command: MutationCommand) -> None:
    if not command.source_event_id:
        raise ValueError("source_event_id is required")
    if command.mutation_type == "inactivate":
        changed = await inactivate_findings_by_name(db, command.case_id, command.name)
        if not changed:
            raise ValueError("Finding not found")
        return
    if command.mutation_type == "verify":
        rows = list(
            (await db.execute(select(DiscoveryFinding).where(DiscoveryFinding.case_id == command.case_id))).scalars()
        )
        found = False
        for row in rows:
            if not getattr(row, "active", True):
                continue
            if normalize_label(row.name) != normalize_label(command.name):
                continue
            row.status = "verified"
            if row.value and "patient_reported" in row.value:
                row.value = row.value.replace("patient_reported", "verified")
            found = True
        if not found:
            raise ValueError("Finding not found")
        return
    draft = FindingDraft(
        kind=command.kind,
        name=command.name,
        value=command.value,
        status="verified" if command.mutation_type == "verify" else None,
        branch=None,
        source=command.source,
    )
    await apply_finding_drafts(
        db,
        command.case_id,
        [draft],
        source_event_id=command.source_event_id,
    )
