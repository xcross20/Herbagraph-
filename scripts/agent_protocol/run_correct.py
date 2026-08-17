#!/usr/bin/env python3
"""Decide whether a Grok correction may run against the current head SHA."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from agent_protocol.auth import select_trusted_review
from agent_protocol.cycle import completed_correction_cycles, next_cycle_number
from agent_protocol.freshness import refuse_stale_write
from agent_protocol.run_architect import comments_from_payload
from agent_protocol.stop import decide_after_review


def load_json(path: str):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def plan_correction(
    *,
    head_sha: str,
    comments_raw: list[dict],
    requested_action: str = "correct",
    pr_number: int,
    task: str,
    live_head_sha: str | None = None,
) -> dict:
    comments = comments_from_payload(comments_raw)
    cycles = completed_correction_cycles(comments)
    result = {
        "run_correction": "false",
        "reason": "no_review",
        "cycle": next_cycle_number(comments),
        "completed_cycles": cycles,
        "reviewed_commit": None,
        "task": task,
    }
    stale = refuse_stale_write(head_sha, live_head_sha or head_sha)
    if stale:
        result["reason"] = stale
        return result
    if requested_action in {"merge", "deploy", "create_secret", "promote_to_main"}:
        result["reason"] = "forbidden_action"
        result["label"] = "founder-decision-required"
        return result
    latest = select_trusted_review(comments, pr_number=pr_number, head_sha=head_sha, task=task)
    if latest is None:
        result["reason"] = "no_trusted_review"
        return result
    result["reviewed_commit"] = latest.reviewed_commit
    decision = decide_after_review(latest, head_sha=head_sha, completed_cycles=cycles)
    result.update(
        {
            "run_correction": "true" if decision.run_correction else "false",
            "reason": decision.reason,
            "label": decision.label,
            "next_owner": decision.next_owner,
            "review_body": latest.raw,
            "task": latest.task,
        }
    )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--comments-json", required=True)
    parser.add_argument("--pr-number", required=True, type=int)
    parser.add_argument("--task", required=True)
    parser.add_argument("--live-head-sha", default="")
    parser.add_argument("--github-output", default=os.environ.get("GITHUB_OUTPUT"))
    args = parser.parse_args(argv)
    result = plan_correction(
        head_sha=args.head_sha.lower(),
        comments_raw=load_json(args.comments_json),
        pr_number=args.pr_number,
        task=args.task,
        live_head_sha=args.live_head_sha or None,
    )
    if args.github_output:
        with open(args.github_output, "a", encoding="utf-8") as handle:
            for key, value in result.items():
                if key == "review_body" and value:
                    handle.write(f"{key}<<EOF\n{value}\nEOF\n")
                elif value is not None:
                    handle.write(f"{key}={value}\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
