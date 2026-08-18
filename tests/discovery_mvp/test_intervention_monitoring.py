"""PR-51: intervention screening and monitoring causal taxonomy."""

from __future__ import annotations

import pytest

from app.discovery.intervention_safety import screen_intervention
from app.discovery.monitoring import classify_monitoring_causal, record_monitoring_event
from app.models.enums import CausalClaimKind, MonitoringOutcomeKind


def test_warfarin_vitamin_k_is_blocked_and_commerce_cannot_promote():
    blocked = screen_intervention(
        intervention="Vitamin K",
        medications=["Warfarin"],
        gold_label=True,
        claim_kind="recommendation",
    )
    assert blocked.allowed is False
    assert blocked.commerce_used is False
    assert any("warfarin" in item for item in blocked.blocks)


def test_missing_medications_are_an_explicit_limitation():
    result = screen_intervention(intervention="ginkgo", medications=None, claim_kind="education")
    assert "missing_medication_data" in result.limitations
    rec = screen_intervention(intervention="ginkgo", medications=None, claim_kind="recommendation")
    assert rec.allowed is False
    assert rec.kind == "clinician_discussion"


def test_temporal_improvement_is_not_supported_causation():
    kind = classify_monitoring_causal(
        exposure="b12",
        adherence="unknown",
        notes="I improved after taking B12",
        outcome_kind=MonitoringOutcomeKind.IMPROVED,
    )
    assert kind is CausalClaimKind.INSUFFICIENT_FOR_CAUSAL_INFERENCE
    attributed = classify_monitoring_causal(
        exposure="b12",
        adherence="taken",
        notes="I think this helped after taking B12",
        outcome_kind=MonitoringOutcomeKind.IMPROVED,
    )
    assert attributed is CausalClaimKind.USER_ATTRIBUTION
    assert attributed is not CausalClaimKind.SUPPORTED_CAUSAL_INFERENCE


@pytest.mark.asyncio
async def test_duplicate_monitoring_is_idempotent_and_writes_observation(db_session):
    import uuid

    from sqlalchemy import select

    from app.models.discovery import DiscoveryCase, DiscoveryFinding
    from app.models.enums import DiscoveryCaseStatus
    from app.models.user import User

    user = User(email=f"mon-{uuid.uuid4().hex[:8]}@example.com", hashed_password="x")
    db_session.add(user)
    await db_session.flush()
    case = DiscoveryCase(
        user_id=user.id,
        presenting_concern="Burning feet after a supplement.",
        status=DiscoveryCaseStatus.OPEN,
    )
    db_session.add(case)
    await db_session.flush()
    first = await record_monitoring_event(
        db_session,
        case_id=case.id,
        target="burning sensation",
        observation_time="2026-08-18",
        outcome_kind=MonitoringOutcomeKind.NO_CHANGE,
        source_event_id="mon-1",
        exposure="b12",
        adherence="taken",
    )
    second = await record_monitoring_event(
        db_session,
        case_id=case.id,
        target="burning sensation",
        observation_time="2026-08-18",
        outcome_kind=MonitoringOutcomeKind.NO_CHANGE,
        source_event_id="mon-1",
        exposure="b12",
        adherence="taken",
    )
    assert first.id == second.id
    assert first.causal_kind is CausalClaimKind.TEMPORAL_ASSOCIATION
    findings = list(
        (
            await db_session.execute(
                select(DiscoveryFinding).where(
                    DiscoveryFinding.case_id == case.id,
                    DiscoveryFinding.name == "monitor:burning sensation",
                )
            )
        ).scalars()
    )
    assert len(findings) == 1
    assert findings[0].value == "no_change"


@pytest.mark.asyncio
async def test_adverse_event_requires_escalation(db_session):
    import uuid

    from app.discovery.monitoring import monitoring_requires_safety_escalation
    from app.models.discovery import DiscoveryCase
    from app.models.enums import DiscoveryCaseStatus
    from app.models.user import User

    user = User(email=f"adv-{uuid.uuid4().hex[:8]}@example.com", hashed_password="x")
    db_session.add(user)
    await db_session.flush()
    case = DiscoveryCase(user_id=user.id, presenting_concern="Burning feet.", status=DiscoveryCaseStatus.OPEN)
    db_session.add(case)
    await db_session.flush()
    event = await record_monitoring_event(
        db_session,
        case_id=case.id,
        target="burning sensation",
        observation_time="2026-08-18",
        outcome_kind=MonitoringOutcomeKind.ADVERSE_EFFECT,
        source_event_id="adv-1",
        exposure="herb-x",
        adherence="taken",
    )
    assert monitoring_requires_safety_escalation(event.outcome_kind) is True
    assert event.causal_claim is False
