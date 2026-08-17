#!/usr/bin/env python3
"""In-process CHANGES_REQUIRED → correction → re-review demonstration.

No GitHub writes, merges, deploys, or secrets. Used as the Issue #7 dry-run.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from agent_protocol.comment import plan_comment_upsert
from agent_protocol.cycle import completed_correction_cycles
from agent_protocol.format import render_architect_review, render_correction_report, render_handoff
from agent_protocol.parse import ArchitectReview, CommentRecord, marker_for_review
from agent_protocol.qualify import PullRequestView, qualify_pull_request
from agent_protocol.stop import decide_after_review

SHA1 = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
SHA2 = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"


def run_dry_run() -> dict:
    pr = PullRequestView(
        number=7,
        base_ref="integration/agent",
        head_ref="grok/7-autonomous-review-loop",
        head_sha=SHA1,
        head_repo="xcross20/Herbagraph-",
        base_repo="xcross20/Herbagraph-",
        labels=frozenset({"agent-loop"}),
        is_fork=False,
    )
    comments: list[CommentRecord] = [
        CommentRecord(
            id=1,
            body=render_handoff(task="HG-7", commit=SHA1, pr_number=7),
            author_login="github-actions[bot]",
        )
    ]
    qualify = qualify_pull_request(pr, handoff_sha=SHA1)
    if not qualify.allowed:
        raise AssertionError(qualify.reason)

    first = ArchitectReview(
        task="HG-7",
        reviewed_commit=SHA1,
        status="CHANGES_REQUIRED",
        blocking=("Document the dry-run loop.",),
        hostile_trace="Relabeling the same SHA must not create a second review.",
        required_checks=("tests/test_agent_protocol",),
        allowed_next_scope="Protocol docs and tests only.",
        next_owner="GROK",
        trap_line="Approval never merges.",
    )
    first_body = render_architect_review(first, pr_number=7)
    first_plan = plan_comment_upsert(
        comments, marker=marker_for_review(7, SHA1), body=first_body
    )
    comments.append(
        CommentRecord(id=2, body=first_plan.body, author_login="github-actions[bot]")
    )
    first_decision = decide_after_review(first, head_sha=SHA1, completed_cycles=0)
    if not first_decision.run_correction:
        raise AssertionError(first_decision.reason)

    duplicate = plan_comment_upsert(
        comments, marker=marker_for_review(7, SHA1), body=first_body
    )
    if duplicate.action == "create":
        raise AssertionError("duplicate delivery created a second review")

    comments.append(
        CommentRecord(
            id=3,
            author_login="github-actions[bot]",
            body=render_correction_report(
                task="HG-7",
                pr_number=7,
                reviewed_commit=SHA1,
                new_commit=SHA2,
                cycle=1,
                tests="pytest tests/test_agent_protocol -q",
            ),
        )
    )
    stale = decide_after_review(first, head_sha=SHA2, completed_cycles=1)
    if stale.run_correction:
        raise AssertionError("stale review triggered correction on a newer SHA")

    approved = ArchitectReview(
        task="HG-7",
        reviewed_commit=SHA2,
        status="ARCHITECT_APPROVED",
        next_owner="FOUNDER",
        trap_line="Approval never merges or deploys.",
    )
    second = decide_after_review(
        approved,
        head_sha=SHA2,
        completed_cycles=completed_correction_cycles(comments),
    )
    if second.run_correction or second.reason != "architect_approved_no_merge":
        raise AssertionError(second)
    return {
        "qualify": qualify.reason,
        "first_verdict": first.status,
        "duplicate_action": duplicate.action,
        "stale_reason": stale.reason,
        "second_reason": second.reason,
        "merged": False,
        "deployed": False,
    }


def main() -> int:
    result = run_dry_run()
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
