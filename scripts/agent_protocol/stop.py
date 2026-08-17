"""Stop-state rules. Automation never merges or deploys."""

from __future__ import annotations

from dataclasses import dataclass

from .constants import (
    FORBIDDEN_ACTIONS,
    MAX_CORRECTION_CYCLES,
    VERDICT_APPROVED,
    VERDICT_CHANGES_REQUIRED,
    VERDICT_FOUNDER,
)
from .parse import ArchitectReview


@dataclass(frozen=True)
class LoopDecision:
    continue_automation: bool
    run_correction: bool
    label: str | None
    reason: str
    next_owner: str


def review_matches_head(review: ArchitectReview, head_sha: str) -> bool:
    return review.reviewed_commit.lower() == (head_sha or "").lower()


def decide_after_review(
    review: ArchitectReview,
    *,
    head_sha: str,
    completed_cycles: int,
    checks_green: bool | None = None,
    checks_state: str | None = None,
) -> LoopDecision:
    if checks_state == "pending":
        return LoopDecision(
            continue_automation=True,
            run_correction=False,
            label=None,
            reason="checks_pending",
            next_owner="NONE",
        )
    if checks_state == "missing":
        return LoopDecision(
            continue_automation=False,
            run_correction=False,
            label="founder-decision-required",
            reason="required_checks_missing",
            next_owner="FOUNDER",
        )
    if checks_state == "failed":
        if review.status == VERDICT_APPROVED:
            review_status = VERDICT_CHANGES_REQUIRED
        else:
            review_status = review.status
        if review_status == VERDICT_CHANGES_REQUIRED and completed_cycles < MAX_CORRECTION_CYCLES:
            return LoopDecision(
                continue_automation=True,
                run_correction=True,
                label="changes-required",
                reason="required_checks_failed",
                next_owner="GROK",
            )
        return LoopDecision(
            continue_automation=False,
            run_correction=False,
            label="founder-decision-required",
            reason="required_checks_failed",
            next_owner="FOUNDER",
        )
    if review.status == VERDICT_APPROVED and checks_green is False:
        return LoopDecision(
            continue_automation=False,
            run_correction=False,
            label="founder-decision-required",
            reason="required_checks_not_green",
            next_owner="FOUNDER",
        )
    if review.status == VERDICT_FOUNDER:
        return LoopDecision(
            continue_automation=False,
            run_correction=False,
            label="founder-decision-required",
            reason="review_requested_founder",
            next_owner="FOUNDER",
        )
    if not review_matches_head(review, head_sha):
        return LoopDecision(
            continue_automation=False,
            run_correction=False,
            label=None,
            reason="stale_review_sha",
            next_owner="NONE",
        )
    if review.status == VERDICT_APPROVED:
        return LoopDecision(
            continue_automation=False,
            run_correction=False,
            label="architect-approved",
            reason="architect_approved_no_merge",
            next_owner="FOUNDER",
        )
    if review.status != VERDICT_CHANGES_REQUIRED:
        return LoopDecision(
            continue_automation=False,
            run_correction=False,
            label="founder-decision-required",
            reason="unrecognized_verdict",
            next_owner="FOUNDER",
        )
    if completed_cycles >= MAX_CORRECTION_CYCLES:
        return LoopDecision(
            continue_automation=False,
            run_correction=False,
            label="founder-decision-required",
            reason="correction_cycle_limit",
            next_owner="FOUNDER",
        )
    return LoopDecision(
        continue_automation=True,
        run_correction=True,
        label="changes-required",
        reason="changes_required",
        next_owner="GROK",
    )


def action_is_forbidden(action: str) -> bool:
    return action in FORBIDDEN_ACTIONS
