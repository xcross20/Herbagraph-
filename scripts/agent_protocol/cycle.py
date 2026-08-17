"""Count completed automated correction cycles on a PR."""

from __future__ import annotations

from .auth import is_trusted_author
from .constants import MAX_CORRECTION_CYCLES, VERDICT_CHANGES_REQUIRED
from .parse import ArchitectReview, CommentRecord, CorrectionReport, parse_architect_review, parse_correction_report


def reviews_from_comments(comments: list[CommentRecord]) -> list[ArchitectReview]:
    found: list[ArchitectReview] = []
    for comment in comments:
        if not is_trusted_author(comment):
            continue
        parsed = parse_architect_review(comment.body)
        if parsed is not None:
            found.append(parsed)
    return found


def corrections_from_comments(comments: list[CommentRecord]) -> list[CorrectionReport]:
    found: list[CorrectionReport] = []
    for comment in comments:
        if not is_trusted_author(comment):
            continue
        parsed = parse_correction_report(comment.body)
        if parsed is not None:
            found.append(parsed)
    return found


def completed_correction_cycles(comments: list[CommentRecord]) -> int:
    """A cycle is a CHANGES_REQUIRED review that already has a correction report."""
    reviews = [item for item in reviews_from_comments(comments) if item.status == VERDICT_CHANGES_REQUIRED]
    corrections = corrections_from_comments(comments)
    matched = 0
    used: set[str] = set()
    for review in reviews:
        for correction in corrections:
            key = f"{correction.reviewed_commit}:{correction.cycle}"
            if correction.reviewed_commit == review.reviewed_commit and key not in used:
                used.add(key)
                matched += 1
                break
    return matched


def next_cycle_number(comments: list[CommentRecord]) -> int:
    existing = [item.cycle for item in corrections_from_comments(comments)]
    return (max(existing) + 1) if existing else 1


def cycles_exhausted(comments: list[CommentRecord]) -> bool:
    return completed_correction_cycles(comments) >= MAX_CORRECTION_CYCLES
