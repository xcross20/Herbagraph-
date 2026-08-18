"""Case-linked monitoring. Temporal change is not causation."""

from __future__ import annotations

import hashlib
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.discovery.intervention_safety import classify_causal_language
from app.discovery.scientific_output import fail_closed_text
from app.models.discovery import DiscoveryMonitoringEvent
from app.models.enums import CausalClaimKind, MonitoringOutcomeKind

ESCALATING = {MonitoringOutcomeKind.ADVERSE_EFFECT, MonitoringOutcomeKind.WORSENED}


def monitoring_identity_key(
    *,
    case_id: uuid.UUID,
    target: str,
    observation_time: str,
    source_event_id: str,
) -> str:
    material = "|".join((str(case_id), target, observation_time, source_event_id))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def classify_monitoring_causal(
    *,
    exposure: str | None,
    adherence: str | None,
    notes: str | None,
    outcome_kind: MonitoringOutcomeKind,
) -> CausalClaimKind:
    blob = (notes or "").lower()
    user_attribution = "i think" in blob or "i believe" in blob or "after taking" in blob
    if outcome_kind is MonitoringOutcomeKind.STOPPED and exposure:
        return CausalClaimKind.DECHALLENGE_SIGNAL
    code = classify_causal_language(
        exposure=exposure,
        adherence=adherence,
        user_attribution=user_attribution,
    )
    return CausalClaimKind(code)


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
    persist_observation: bool = True,
) -> DiscoveryMonitoringEvent:
    if notes:
        blob = notes.lower()
        if "caused" in blob and "not caused" not in blob:
            raise ValueError("monitoring_notes_must_not_claim_causation")
        checked = fail_closed_text(notes, provenance=["monitoring"])
        if checked != notes:
            raise ValueError("monitoring_notes_must_not_claim_causation")
    identity = monitoring_identity_key(
        case_id=case_id,
        target=target,
        observation_time=observation_time,
        source_event_id=source_event_id,
    )
    existing = (
        await db.execute(
            select(DiscoveryMonitoringEvent).where(
                DiscoveryMonitoringEvent.case_id == case_id,
                DiscoveryMonitoringEvent.identity_key == identity,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    causal_kind = classify_monitoring_causal(
        exposure=exposure,
        adherence=adherence,
        notes=notes,
        outcome_kind=outcome_kind,
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
        causal_kind=causal_kind,
    )
    db.add(event)
    await db.flush()
    if persist_observation:
        from app.discovery.commands import MutationCommand, apply_command

        await apply_command(
            db,
            MutationCommand(
                case_id=case_id,
                source_event_id=f"monitor:{source_event_id}",
                actor="system",
                mutation_type="assert",
                name=f"monitor:{target}",
                value=outcome_kind.value,
                kind="assessment",
                source="monitoring",
            ),
        )
        await db.flush()
    return event


def monitoring_requires_safety_escalation(outcome_kind: MonitoringOutcomeKind) -> bool:
    return outcome_kind in ESCALATING
