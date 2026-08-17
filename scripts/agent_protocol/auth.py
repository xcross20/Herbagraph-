"""Authenticate protocol comments. User forgeries cannot trigger Grok."""

from __future__ import annotations

from .parse import ArchitectReview, CommentRecord, parse_architect_review


def is_trusted_author(comment: CommentRecord) -> bool:
    """Bot login is shared across workflows and is never sufficient alone."""
    del comment
    return False


def select_trusted_review(
    comments: list[CommentRecord],
    *,
    pr_number: int,
    head_sha: str,
    task: str,
    artifact=None,
    workflow_run_id: str | None = None,
    trusted_workflow_sha: str | None = None,
) -> ArchitectReview | None:
    if artifact is None:
        return None
    if not artifact.matches(
        pr_number=pr_number,
        head_sha=head_sha,
        task=task,
        workflow_run_id=workflow_run_id,
        trusted_workflow_sha=trusted_workflow_sha,
    ):
        return None
    return parse_review_from_payload(artifact.review_payload, head_sha=head_sha, task=task)


def parse_review_from_payload(payload: str, *, head_sha: str, task: str) -> ArchitectReview | None:
    from .parse import parse_review_json

    parsed = parse_review_json(payload)
    if parsed is None:
        return parse_architect_review(payload, expected_sha=head_sha, expected_task=task)
    if parsed.reviewed_commit.lower() != head_sha.lower():
        return None
    if parsed.task not in {"", "UNKNOWN", task}:
        return None
    return parsed
