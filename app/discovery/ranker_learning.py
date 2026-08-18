"""Record ranker acceptance without changing scientific rules."""

from __future__ import annotations

import json
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.discovery import DiscoveryTurn
from app.models.enums import DiscoveryTurnRole

LEGAL_DECISIONS = frozenset({"accepted", "deferred", "completed", "declined"})


async def record_ranker_decision(
    db: AsyncSession,
    *,
    case_id: uuid.UUID,
    decision: str,
    gap_code: str | None,
    source_event_id: str,
) -> DiscoveryTurn:
    if decision not in LEGAL_DECISIONS:
        raise ValueError("unknown_ranker_decision")
    turn = DiscoveryTurn(
        case_id=case_id,
        role=DiscoveryTurnRole.SYSTEM,
        text=f"Ranker learning event: {decision}",
        kind="ranker_learning",
        payload=json.dumps(
            {
                "decision": decision,
                "gap_code": gap_code,
                "changes_scientific_rules": False,
                "source_event_id": source_event_id,
            }
        ),
        idempotency_key=source_event_id,
    )
    db.add(turn)
    await db.flush()
    return turn
