"""Issue 62: consented decision-impact events. Do not train the ranker from these."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone


ALLOWED_PURPOSES = frozenset({"direct_service", "quality_improvement", "research"})


@dataclass
class DecisionLog:
    events: list[dict] = field(default_factory=list)
    consent_purpose: str = "direct_service"
    secondary_use_allowed: bool = False

    def as_dict(self) -> dict:
        return {
            "events": list(self.events),
            "consent_purpose": self.consent_purpose,
            "secondary_use_allowed": self.secondary_use_allowed,
        }

    @classmethod
    def from_dict(cls, payload: dict | None) -> DecisionLog:
        data = payload or {}
        return cls(
            events=list(data.get("events") or []),
            consent_purpose=str(data.get("consent_purpose") or "direct_service"),
            secondary_use_allowed=bool(data.get("secondary_use_allowed")),
        )


def hashed_source(text: str) -> str:
    """Stable event key. Never persist the raw user turn."""
    return hashlib.sha256((text or "turn").encode("utf-8")).hexdigest()[:24]


def event_identity(source_event_id: str, selected_id: str | None) -> str:
    material = f"{source_event_id}|{selected_id or 'none'}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]


def record_decision(
    log: DecisionLog,
    *,
    source_event_id: str,
    response_mode: str | None,
    candidates: list[dict],
    selected_id: str | None,
    map_version: int | None = None,
    purpose: str = "direct_service",
) -> DecisionLog:
    if purpose not in ALLOWED_PURPOSES:
        purpose = "direct_service"
    identity = event_identity(source_event_id, selected_id)
    if any(item.get("identity") == identity for item in log.events):
        return log
    snapshots = []
    for index, item in enumerate(candidates):
        snapshots.append(
            {
                "candidate_id": item.get("id") or item.get("code"),
                "label": item.get("label"),
                "modality": item.get("modality"),
                "information_value": item.get("information_value") or item.get("score"),
                "displayed_rank": index + 1,
                "scientific_rank": index + 1,
                "filter_reason": item.get("rejected_reason"),
                "why": item.get("explanation"),
            }
        )
    log.events.append(
        {
            "identity": identity,
            "source_event_id": source_event_id,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "response_mode": response_mode,
            "selected_id": selected_id,
            "map_version": map_version,
            "consent_purpose": purpose,
            "secondary_use_allowed": log.secondary_use_allowed and purpose != "direct_service",
            "candidates": snapshots,
            "changes_scientific_rank": False,
        }
    )
    return log


def dumps(log: DecisionLog) -> str:
    return json.dumps(log.as_dict())
