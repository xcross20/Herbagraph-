"""Case-linked monitoring. Temporal change is not causation."""

from __future__ import annotations

import hashlib
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.discovery import DiscoveryMonitoringEvent
from app.models.enums import MonitoringOutcomeKind


def monitoring_identity_key(
    *,
    case_id: uuid.UUID,
    target: str,
    observation_time: str,
    source_event_id: str,
) -> str:
    material = "|".join((str(case_id), target, observation_time, source_event_id))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


async def record_monitoring_event(
    db: AsyncSession,
    *,
    case_id: uuid.UUID,
    target: str,
    observation_time: str,
    outcome_kind: MonitoringOutcomeKind,
    source_event_id: str,
    exposure: str | None = None,
    adherence: str | None = None,
    notes: str | None = None,
) -> DiscoveryMonitoringEvent:
    if outcome_kind is MonitoringOutcomeKind.IMPROVED and notes and "caused" in notes.lower():
        raise ValueError("monitoring_notes_must_not_claim_causation")
    identity = monitoring_identity_key(
        case_id=case_id,
        target=target,
        observation_time=observation_time,
        source_event_id=source_event_id,
    )
    event = DiscoveryMonitoringEvent(
        case_id=case_id,
        target=target,
        observation_time=observation_time,
        outcome_kind=outcome_kind,
        exposure=exposure,
        adherence=adherence,
        notes=notes,
        source_event_id=source_event_id,
        identity_key=identity,
        causal_claim=False,
    )
    db.add(event)
    await db.flush()
    return event
