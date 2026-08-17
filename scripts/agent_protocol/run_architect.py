#!/usr/bin/env python3
"""Qualify a PR and plan the Codex review upsert for the current head SHA."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from agent_protocol.artifact import ReviewArtifact, artifact_from_dict
from agent_protocol.checks import apply_check_gate, parse_check_runs
from agent_protocol.comment import plan_comment_upsert
from agent_protocol.cycle import completed_correction_cycles
from agent_protocol.format import render_architect_review
from agent_protocol.freshness import refuse_stale_write
from agent_protocol.parse import (
    ArchitectReview,
    CommentRecord,
    parse_handoff,
    parse_review_json,
    marker_for_review,
)
from agent_protocol.qualify import PullRequestView, qualify_pull_request
from agent_protocol.stop import decide_after_review


def load_json(path: str):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def comments_from_payload(raw: list[dict]) -> list[CommentRecord]:
    records: list[CommentRecord] = []
    for item in raw or []:
        user = item.get("user") or {}
        records.append(
            CommentRecord(
                id=item.get("id"),
                body=item.get("body") or "",
                author_login=str(user.get("login") or item.get("author_login") or ""),
                author_type=str(user.get("type") or item.get("author_type") or ""),
            )
        )
    return records


def labels_from_payload(raw) -> frozenset[str]:
    names: list[str] = []
    for item in raw or []:
        if isinstance(item, str):
            names.append(item)
        elif isinstance(item, dict) and item.get("name"):
            names.append(str(item["name"]))
    return frozenset(names)


def pull_request_from_payload(pr_raw: dict) -> PullRequestView:
    head = pr_raw.get("head") or {}
    base = pr_raw.get("base") or {}
    head_repo = (head.get("repo") or {}).get("full_name") or pr_raw.get("head_repo") or ""
    base_repo = (base.get("repo") or {}).get("full_name") or pr_raw.get("base_repo") or ""
    return PullRequestView(
        number=int(pr_raw.get("number")),
        base_ref=base.get("ref") or pr_raw.get("base_ref") or "",
        head_ref=head.get("ref") or pr_raw.get("head_ref") or "",
        head_sha=(head.get("sha") or pr_raw.get("head_sha") or "").lower(),
        head_repo=head_repo,
        base_repo=base_repo,
        labels=labels_from_payload(pr_raw.get("labels")),
        is_fork=bool((head.get("repo") or {}).get("fork")) or (head_repo != base_repo and bool(head_repo)),
    )


def latest_handoff(comments: list[CommentRecord], pr_body: str, head_sha: str):
    matches = [parsed for comment in comments if (parsed := parse_handoff(comment.body)) and parsed.commit == head_sha]
    if matches:
        return matches[-1]
    body_handoff = parse_handoff(pr_body or "")
    if body_handoff is not None and body_handoff.commit == head_sha:
        return body_handoff
    return None


def plan_architect_action(
    pr_raw: dict,
    comments_raw: list[dict],
    review_text: str,
    *,
    live_head_sha: str | None = None,
    checks_raw: dict | list | None = None,
    artifact: ReviewArtifact | None = None,
) -> dict:
    comments = comments_from_payload(comments_raw)
    pr = pull_request_from_payload(pr_raw)
    handoff = latest_handoff(comments, pr_raw.get("body") or "", pr.head_sha)
    qualify = qualify_pull_request(pr, handoff_sha=handoff.commit if handoff else None)
    task = handoff.task if handoff else ""
    result = {
        "qualified": qualify.allowed,
        "qualify_reason": qualify.reason,
        "run_correction": "false",
        "verdict": None,
        "label": None,
        "upsert_action": "noop",
        "comment_body": None,
        "comment_id": None,
        "reason": qualify.reason,
        "head_sha": pr.head_sha,
        "pr_number": pr.number,
        "task": task,
    }
    stale = refuse_stale_write(pr.head_sha, live_head_sha or pr.head_sha)
    if stale:
        result["reason"] = stale
        return result
    if not qualify.allowed:
        return result
    if not task:
        result["reason"] = "handoff_task_missing"
        result["label"] = "founder-decision-required"
        return result

    review = parse_review_json(review_text)
    if review is None:
        result["reason"] = "review_unparseable"
        result["label"] = "founder-decision-required"
        return result
    if review.reviewed_commit != pr.head_sha:
        result["reason"] = "review_sha_mismatch"
        result["label"] = "founder-decision-required"
        return result
    if review.task in {"", "UNKNOWN"}:
        review = ArchitectReview(
            task=task,
            reviewed_commit=review.reviewed_commit,
            status=review.status,
            blocking=review.blocking,
            should_fix=review.should_fix,
            noted=review.noted,
            hostile_trace=review.hostile_trace,
            required_checks=review.required_checks,
            allowed_next_scope=review.allowed_next_scope,
            next_owner=review.next_owner,
            trap_line=review.trap_line,
            raw=review.raw,
        )
    elif review.task != task:
        result["reason"] = "review_task_mismatch"
        result["label"] = "founder-decision-required"
        return result

    checks = parse_check_runs(checks_raw or [])
    gate = apply_check_gate(review.status, checks)
    if gate["state"] == "pending":
        result.update({"reason": "checks_pending", "verdict": review.status, "upsert_action": "noop"})
        return result
    coerced = gate["status"]
    if coerced != review.status:
        review = ArchitectReview(
            task=review.task,
            reviewed_commit=review.reviewed_commit,
            status=coerced,
            blocking=review.blocking + (gate["reason"],),
            should_fix=review.should_fix,
            noted=review.noted,
            hostile_trace=review.hostile_trace,
            required_checks=review.required_checks,
            allowed_next_scope=review.allowed_next_scope,
            next_owner="GROK" if coerced == "CHANGES_REQUIRED" else "FOUNDER",
            trap_line=review.trap_line or "Approval is impossible while required checks are missing or failing.",
            raw=review.raw,
        )

    rendered = render_architect_review(review, pr_number=pr.number)
    plan = plan_comment_upsert(comments, marker=marker_for_review(pr.number, pr.head_sha), body=rendered)
    decision = decide_after_review(
        review,
        head_sha=pr.head_sha,
        completed_cycles=completed_correction_cycles(comments),
        checks_green=gate["state"] == "success",
        checks_state=gate["state"],
    )
    result.update(
        {
            "verdict": review.status,
            "run_correction": "true" if decision.run_correction else "false",
            "label": decision.label,
            "upsert_action": "noop" if gate["write"] == "false" else plan.action,
            "comment_body": None if gate["write"] == "false" else plan.body,
            "comment_id": plan.comment_id,
            "reason": decision.reason,
            "next_owner": decision.next_owner,
            "task": review.task,
            "checks_state": gate["state"],
            "artifact_digest": artifact.digest if artifact else "",
        }
    )
    return result


def write_github_output(path: str | None, result: dict) -> None:
    if not path:
        return
    with open(path, "a", encoding="utf-8") as handle:
        for key, value in result.items():
            if key == "comment_body" and value:
                handle.write(f"{key}<<EOF\n{value}\nEOF\n")
            elif value is not None:
                handle.write(f"{key}={value}\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pr-json", required=True)
    parser.add_argument("--comments-json", required=True)
    parser.add_argument("--review-input", required=True)
    parser.add_argument("--live-head-sha", default="")
    parser.add_argument("--checks-json", default="")
    parser.add_argument("--github-output", default=os.environ.get("GITHUB_OUTPUT"))
    args = parser.parse_args(argv)
    checks = load_json(args.checks_json) if args.checks_json else []
    raw_input = Path(args.review_input).read_text(encoding="utf-8")
    artifact = None
    try:
        wrapped = json.loads(raw_input)
    except json.JSONDecodeError:
        wrapped = None
    if isinstance(wrapped, dict) and "review_payload" in wrapped:
        artifact = artifact_from_dict(wrapped)
        raw_input = artifact.review_payload
    result = plan_architect_action(
        load_json(args.pr_json),
        load_json(args.comments_json),
        raw_input,
        live_head_sha=args.live_head_sha or None,
        checks_raw=checks,
        artifact=artifact,
    )
    write_github_output(args.github_output, result)
    print(json.dumps({k: v for k, v in result.items() if k != "comment_body"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
