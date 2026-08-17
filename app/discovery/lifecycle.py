"""Branch lifecycle governor (ADR-MVP-005). No status writes outside this module."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.models.enums import BranchLifecycleStatus, CoverageRelation, EvidenceRelationship

LEGAL: dict[BranchLifecycleStatus, frozenset[BranchLifecycleStatus]] = {
    BranchLifecycleStatus.NOT_EVALUATED: frozenset(
        {
            BranchLifecycleStatus.PARTIALLY_EVALUATED,
            BranchLifecycleStatus.EVALUATED_OPEN,
            BranchLifecycleStatus.CLOSED,
        }
    ),
    BranchLifecycleStatus.PARTIALLY_EVALUATED: frozenset(
        {BranchLifecycleStatus.EVALUATED_OPEN, BranchLifecycleStatus.CLOSED}
    ),
    BranchLifecycleStatus.EVALUATED_OPEN: frozenset(
        {BranchLifecycleStatus.PARTIALLY_EVALUATED, BranchLifecycleStatus.CLOSED}
    ),
    BranchLifecycleStatus.CLOSED: frozenset({BranchLifecycleStatus.REOPENED}),
    BranchLifecycleStatus.REOPENED: frozenset(
        {
            BranchLifecycleStatus.PARTIALLY_EVALUATED,
            BranchLifecycleStatus.EVALUATED_OPEN,
            BranchLifecycleStatus.CLOSED,
        }
    ),
}


@dataclass(frozen=True)
class TransitionDecision:
    accepted: bool
    status: BranchLifecycleStatus
    resolved_at: str | None
    reason: str


def can_close(*, coverage: CoverageRelation, relationship: EvidenceRelationship | None) -> bool:
    if coverage is not CoverageRelation.DIRECTLY_ASSESSES:
        return False
    return relationship is EvidenceRelationship.RESOLVES_GAP


def propose_transition(
    current: BranchLifecycleStatus,
    proposed: BranchLifecycleStatus,
    *,
    coverage: CoverageRelation | None = None,
    relationship: EvidenceRelationship | None = None,
    explicit_reopen: bool = False,
) -> TransitionDecision:
    if proposed is current:
        return TransitionDecision(True, current, None, "idempotent")
    if proposed not in LEGAL[current]:
        return TransitionDecision(False, current, None, "illegal_transition")
    if proposed is BranchLifecycleStatus.CLOSED:
        if coverage is None or not can_close(coverage=coverage, relationship=relationship):
            return TransitionDecision(False, current, None, "coverage_does_not_justify_close")
        stamp = datetime.now(timezone.utc).isoformat()
        return TransitionDecision(True, proposed, stamp, "closed_by_resolving_evidence")
    if proposed is BranchLifecycleStatus.REOPENED and not explicit_reopen:
        return TransitionDecision(False, current, None, "reopen_requires_explicit_rule")
    return TransitionDecision(True, proposed, None, "accepted")
