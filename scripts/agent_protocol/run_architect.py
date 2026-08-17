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

from agent_protocol.comment import plan_comment_upsert
from agent_protocol.cycle import completed_correction_cycles
from agent_protocol.format import render_architect_review
from agent_protocol.parse import (
    CommentRecord,
    parse_architect_review,
    parse_handoff,
    parse_review_json,
    marker_for_review,
)
from agent_protocol.qualify import PullRequestView, qualify_pull_request
from agent_protocol.stop import decide_after_review


def load_json(path: str):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def comments_from_payload(raw: list[dict]) -> list[CommentRecord]:
    return [CommentRecord(id=item.get("id"), body=item.get("body") or "") for item in raw]


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


def plan_architect_action(pr_raw: dict, comments_raw: list[dict], review_text: str) -> dict:
    comments = comments_from_payload(comments_raw)
    pr = pull_request_from_payload(pr_raw)
    handoff = latest_handoff(comments, pr_raw.get("body") or "", pr.head_sha)
    qualify = qualify_pull_request(pr, handoff_sha=handoff.commit if handoff else None)
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
        "task": handoff.task if handoff else "HG-7",
    }
    if not qualify.allowed:
        return result

    review = parse_review_json(review_text) or parse_architect_review(review_text)
    if review is None:
        result["reason"] = "review_unparseable"
        result["label"] = "founder-decision-required"
        return result
    if review.reviewed_commit != pr.head_sha:
        result["reason"] = "review_sha_mismatch"
        result["label"] = "founder-decision-required"
        return result

    rendered = render_architect_review(review, pr_number=pr.number)
    plan = plan_comment_upsert(comments, marker=marker_for_review(pr.number, pr.head_sha), body=rendered)
    decision = decide_after_review(
        review,
        head_sha=pr.head_sha,
        completed_cycles=completed_correction_cycles(comments),
    )
    result.update(
        {
            "verdict": review.status,
            "run_correction": "true" if decision.run_correction else "false",
            "label": decision.label,
            "upsert_action": plan.action,
            "comment_body": plan.body,
            "comment_id": plan.comment_id,
            "reason": decision.reason,
            "next_owner": decision.next_owner,
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
    parser.add_argument("--github-output", default=os.environ.get("GITHUB_OUTPUT"))
    args = parser.parse_args(argv)
    result = plan_architect_action(
        load_json(args.pr_json),
        load_json(args.comments_json),
        Path(args.review_input).read_text(encoding="utf-8"),
    )
    write_github_output(args.github_output, result)
    print(json.dumps({k: v for k, v in result.items() if k != "comment_body"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
