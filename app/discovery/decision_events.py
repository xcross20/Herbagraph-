"""Issue 62: consented decision-impact events. Do not train the ranker from these."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone


ALLOWED_PURPOSES = frozenset({"direct_service", "quality_improvement", "research"})
NON_ADDRESSING = frozenset({"does_not_directly_assess", "does_not_address", "unknown"})
DELTA_KINDS = (
    "opened",
    "supported",
    "weakened",
    "partially_assessed",
    "closed",
    "reopened",
    "unchanged",
    "non_addressing",
)
DISPOSITIONS = frozenset(
    {
        "displayed",
        "selected_by_system",
        "accepted",
        "deferred",
        "declined",
        "clinician_selected",
        "not_completed",
        "unavailable",
        "completion_unknown",
    }
)


def events_enabled() -> bool:
    from app.config import get_settings

    settings = get_settings()
    env = (getattr(settings, "app_env", "") or "").lower()
    if env in {"uat", "preview"}:
        return True
    return bool(getattr(settings, "decision_impact_events_v1", False))


@dataclass
class DecisionLog:
    events: list[dict] = field(default_factory=list)
    outcomes: list[dict] = field(default_factory=list)
    dispositions: list[dict] = field(default_factory=list)
    consent_purpose: str = "direct_service"
    secondary_use_allowed: bool = False
    instrumentation_failures: int = 0

    def as_dict(self) -> dict:
        return {
            "events": list(self.events),
            "outcomes": list(self.outcomes),
            "dispositions": list(self.dispositions),
            "consent_purpose": self.consent_purpose,
            "secondary_use_allowed": self.secondary_use_allowed,
            "instrumentation_failures": self.instrumentation_failures,
        }

    @classmethod
    def from_dict(cls, payload: dict | None) -> DecisionLog:
        data = payload or {}
        return cls(
            events=list(data.get("events") or []),
            outcomes=list(data.get("outcomes") or []),
            dispositions=list(data.get("dispositions") or []),
            consent_purpose=str(data.get("consent_purpose") or "direct_service"),
            secondary_use_allowed=bool(data.get("secondary_use_allowed")),
            instrumentation_failures=int(data.get("instrumentation_failures") or 0),
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


def compute_map_delta(*, coverage: str | None, usable: bool, prior_status: str | None = None) -> dict:
    """Governed branch transition. Narrative never chooses the kind."""
    del prior_status
    if not usable:
        return {"kind": "unchanged", "reason": "failed_or_indeterminate"}
    relation = str(coverage or "unknown")
    if relation in NON_ADDRESSING:
        return {"kind": "non_addressing", "reason": "evidence_does_not_address"}
    if relation in {"partially_assesses", "may_support", "may_support_but_is_nonspecific"}:
        return {"kind": "partially_assessed", "reason": "partial_coverage"}
    if relation in {"directly_assesses", "assesses", "supports"}:
        return {"kind": "supported", "reason": "addressing_coverage"}
    if relation in {"weakens"}:
        return {"kind": "weakened", "reason": "weakening_coverage"}
    return {"kind": "unchanged", "reason": "unclassified_coverage"}


def record_disposition(
    log: DecisionLog,
    *,
    event_identity: str,
    disposition: str,
    source_event_id: str,
    reason_category: str | None = None,
) -> DecisionLog:
    if disposition not in DISPOSITIONS:
        disposition = "completion_unknown"
    if any(item.get("source_event_id") == source_event_id for item in log.dispositions):
        return log
    log.dispositions.append(
        {
            "event_identity": event_identity,
            "disposition": disposition,
            "reason_category": reason_category,
            "source_event_id": source_event_id,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    return log


def link_later_evidence(
    log: DecisionLog,
    *,
    evidence_id: str,
    coverage: str | None,
    branch_id: str | None,
    usable: bool = True,
    source_event_id: str | None = None,
    selected_id: str | None = None,
) -> DecisionLog:
    """Link a later result to at most one prior decision. Ambiguous matches stay unresolved."""
    if source_event_id and any(item.get("source_event_id") == source_event_id for item in log.outcomes):
        return log
    matches = []
    for event in log.events:
        if selected_id and event.get("selected_id") == selected_id:
            matches.append(event)
            continue
        candidate_ids = {row.get("candidate_id") for row in (event.get("candidates") or [])}
        if selected_id and selected_id in candidate_ids:
            matches.append(event)
    if selected_id is None:
        matches = list(log.events) if len(log.events) == 1 else []
    if len(matches) != 1:
        log.outcomes.append(
            {
                "identity": event_identity(source_event_id or evidence_id, selected_id),
                "source_event_id": source_event_id or evidence_id,
                "evidence_id": evidence_id,
                "linked_decision": None,
                "link_state": "unresolved_ambiguous" if len(matches) > 1 else "unresolved_missing",
                "map_delta": compute_map_delta(coverage=coverage, usable=usable),
                "branch_id": branch_id,
                "usable": usable,
            }
        )
        return log
    event = matches[0]
    delta = compute_map_delta(coverage=coverage, usable=usable)
    log.outcomes.append(
        {
            "identity": event_identity(source_event_id or evidence_id, event.get("selected_id")),
            "source_event_id": source_event_id or evidence_id,
            "evidence_id": evidence_id,
            "linked_decision": event.get("identity"),
            "link_state": "linked",
            "map_delta": delta,
            "branch_id": branch_id,
            "usable": usable,
            "closes_branch": False,
        }
    )
    return log


def withdraw_secondary_use(log: DecisionLog) -> DecisionLog:
    log.secondary_use_allowed = False
    for event in log.events:
        event["secondary_use_allowed"] = False
    return log


def founder_uat_view(log: DecisionLog) -> dict:
    """PHI-safe completeness view. No health text, identifiers, or citations."""
    deltas = [item.get("map_delta") or {} for item in log.outcomes]
    return {
        "event_count": len(log.events),
        "outcome_count": len(log.outcomes),
        "disposition_count": len(log.dispositions),
        "linked_outcome_count": sum(1 for item in log.outcomes if item.get("link_state") == "linked"),
        "valid_map_delta_count": sum(1 for item in deltas if item.get("kind") in DELTA_KINDS),
        "non_addressing_count": sum(1 for item in deltas if item.get("kind") == "non_addressing"),
        "correction_count": sum(1 for item in log.dispositions if item.get("disposition") == "clinician_selected"),
        "consent_eligible_count": sum(1 for item in log.events if item.get("secondary_use_allowed")),
        "consent_ineligible_count": sum(1 for item in log.events if not item.get("secondary_use_allowed")),
        "instrumentation_failures": log.instrumentation_failures,
        "candidate_set_complete": all(item.get("candidates") for item in log.events) if log.events else False,
        "contains_raw_health_text": False,
        "changes_scientific_rank": False,
    }


def dumps(log: DecisionLog) -> str:
    return json.dumps(log.as_dict())
