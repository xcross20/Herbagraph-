"""Render durable review, handoff, and correction comments."""

from __future__ import annotations

from .constants import (
    CORRECTION_HEADING,
    HANDOFF_HEADING,
    REVIEW_HEADING,
    VERDICT_APPROVED,
    VERDICT_CHANGES_REQUIRED,
)
from .parse import ArchitectReview, marker_for_correction, marker_for_handoff, marker_for_review


def _bullets(items: tuple[str, ...] | list[str]) -> str:
    values = [item.strip() for item in items if item and item.strip()]
    if not values:
        return "1. None"
    return "\n".join(f"{index}. {item}" for index, item in enumerate(values, start=1))


def render_architect_review(review: ArchitectReview, *, pr_number: int) -> str:
    marker = marker_for_review(pr_number, review.reviewed_commit)
    next_owner = review.next_owner or (
        "GROK" if review.status == VERDICT_CHANGES_REQUIRED else "FOUNDER"
    )
    unresolved = 0 if review.status == VERDICT_APPROVED else len(review.blocking)
    return f"""{marker}
{REVIEW_HEADING}
Task: {review.task}
Reviewed commit: {review.reviewed_commit}
Status: {review.status}
Unresolved blocking findings: {unresolved}
Next owner: {next_owner}

BLOCKING:
{_bullets(review.blocking)}

SHOULD-FIX:
{_bullets(review.should_fix)}

NOTED:
{_bullets(review.noted)}

HOSTILE TRACE:
{_bullets((review.hostile_trace,) if review.hostile_trace else ())}

REQUIRED CHECKS:
{_bullets(review.required_checks)}

ALLOWED NEXT SCOPE:
{_bullets((review.allowed_next_scope,) if review.allowed_next_scope else ())}

TRAP LINE:
{_bullets((review.trap_line,) if review.trap_line else ())}
"""


def render_handoff(*, task: str, commit: str, pr_number: int, status: str = "READY_FOR_ARCHITECT") -> str:
    marker = marker_for_handoff(pr_number, commit)
    return f"""{marker}
{HANDOFF_HEADING}
Task: {task}
Status: {status}
Commit: {commit}
"""


def render_correction_report(
    *,
    task: str,
    pr_number: int,
    reviewed_commit: str,
    new_commit: str,
    cycle: int,
    tests: str,
) -> str:
    marker = marker_for_correction(pr_number, reviewed_commit)
    return f"""{marker}
{CORRECTION_HEADING}
Task: {task}
Status: READY_FOR_ARCHITECT
Reviewed commit: {reviewed_commit}
Commit: {new_commit}
Correction-cycle: {cycle}

Tests run:
- {tests}

Migrations:
- None

Security/privacy impact:
- None

Next owner: CODEX
"""
