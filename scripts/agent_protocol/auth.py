"""Authenticate protocol comments. User forgeries cannot trigger Grok."""

from __future__ import annotations

from .constants import TRUSTED_REVIEW_AUTHORS
from .parse import (
    ArchitectReview,
    CommentRecord,
    marker_for_review,
    parse_architect_review,
)


def is_trusted_author(comment: CommentRecord) -> bool:
    login = (comment.author_login or "").lower()
    return login in {name.lower() for name in TRUSTED_REVIEW_AUTHORS}


def select_trusted_review(
    comments: list[CommentRecord],
    *,
    pr_number: int,
    head_sha: str,
    task: str,
) -> ArchitectReview | None:
    marker = marker_for_review(pr_number, head_sha)
    selected: ArchitectReview | None = None
    for comment in comments:
        if not is_trusted_author(comment):
            continue
        parsed = parse_architect_review(
            comment.body,
            expected_marker=marker,
            expected_sha=head_sha,
            expected_task=task,
        )
        if parsed is not None:
            selected = parsed
    return selected
