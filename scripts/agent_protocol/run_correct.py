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

from agent_protocol.cycle import completed_correction_cycles, next_cycle_number
from agent_protocol.parse import CommentRecord, parse_architect_review
from agent_protocol.stop import decide_after_review, review_matches_head


def load_json(path: str):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def plan_correction(
    *,
    head_sha: str,
    comments_raw: list[dict],
    requested_action: str = "correct",
) -> dict:
    comments = [CommentRecord(id=item.get("id"), body=item.get("body") or "") for item in comments_raw]
    reviews = [parsed for item in comments if (parsed := parse_architect_review(item.body))]
    latest = reviews[-1] if reviews else None
    cycles = completed_correction_cycles(comments)
    result = {
        "run_correction": "false",
        "reason": "no_review",
        "cycle": next_cycle_number(comments),
        "completed_cycles": cycles,
        "reviewed_commit": None,
    }
    if requested_action in {"merge", "deploy", "create_secret", "promote_to_main"}:
        result["reason"] = "forbidden_action"
        result["label"] = "founder-decision-required"
        return result
    if latest is None:
        return result
    result["reviewed_commit"] = latest.reviewed_commit
    if not review_matches_head(latest, head_sha):
        result["reason"] = "stale_review_sha"
        return result
    decision = decide_after_review(latest, head_sha=head_sha, completed_cycles=cycles)
    result.update(
        {
            "run_correction": "true" if decision.run_correction else "false",
            "reason": decision.reason,
            "label": decision.label,
            "next_owner": decision.next_owner,
        }
    )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--comments-json", required=True)
    parser.add_argument("--github-output", default=os.environ.get("GITHUB_OUTPUT"))
    args = parser.parse_args(argv)
    result = plan_correction(head_sha=args.head_sha.lower(), comments_raw=load_json(args.comments_json))
    if args.github_output:
        with open(args.github_output, "a", encoding="utf-8") as handle:
            for key, value in result.items():
                if value is not None:
                    handle.write(f"{key}={value}\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
