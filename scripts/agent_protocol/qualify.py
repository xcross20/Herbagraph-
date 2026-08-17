"""Decide whether a pull request may enter the autonomous loop."""

from __future__ import annotations

from dataclasses import dataclass

from .constants import (
    EXCLUDED_HEAD_REFS,
    REQUIRED_BASE_BRANCH,
    REQUIRED_HEAD_PREFIX,
    REQUIRED_LABEL,
)


@dataclass(frozen=True)
class PullRequestView:
    number: int
    base_ref: str
    head_ref: str
    head_sha: str
    head_repo: str
    base_repo: str
    labels: frozenset[str]
    is_fork: bool


@dataclass(frozen=True)
class QualifyResult:
    allowed: bool
    reason: str


def qualify_pull_request(pr: PullRequestView, *, handoff_sha: str | None) -> QualifyResult:
    if pr.is_fork or pr.head_repo != pr.base_repo:
        return QualifyResult(False, "fork_prs_cannot_access_agent_secrets")
    if pr.base_ref != REQUIRED_BASE_BRANCH:
        return QualifyResult(False, f"base_must_be_{REQUIRED_BASE_BRANCH}")
    if not pr.head_ref.startswith(REQUIRED_HEAD_PREFIX):
        return QualifyResult(False, "head_must_be_grok_branch")
    if pr.head_ref in EXCLUDED_HEAD_REFS:
        return QualifyResult(False, "head_explicitly_excluded_from_rollout")
    if REQUIRED_LABEL not in pr.labels:
        return QualifyResult(False, f"missing_label_{REQUIRED_LABEL}")
    if not pr.head_sha or len(pr.head_sha) < 40:
        return QualifyResult(False, "head_sha_must_be_full")
    if not handoff_sha:
        return QualifyResult(False, "handoff_must_identify_head_sha")
    if handoff_sha != pr.head_sha:
        return QualifyResult(False, "handoff_sha_does_not_match_head")
    return QualifyResult(True, "qualified")
