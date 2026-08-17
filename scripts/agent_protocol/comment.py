"""Idempotent PR comment upsert for a PR number + head SHA."""

from __future__ import annotations

from dataclasses import dataclass

from .parse import CommentRecord, find_comment_with_marker


@dataclass(frozen=True)
class UpsertPlan:
    action: str
    comment_id: int | None
    body: str
    marker: str


def plan_comment_upsert(
    comments: list[CommentRecord],
    *,
    marker: str,
    body: str,
) -> UpsertPlan:
    if marker not in body:
        body = f"{marker}\n{body}".rstrip() + "\n"
    existing = find_comment_with_marker(comments, marker)
    if existing is None:
        return UpsertPlan(action="create", comment_id=None, body=body, marker=marker)
    if existing.body.strip() == body.strip():
        return UpsertPlan(action="noop", comment_id=existing.id, body=body, marker=marker)
    return UpsertPlan(action="update", comment_id=existing.id, body=body, marker=marker)
