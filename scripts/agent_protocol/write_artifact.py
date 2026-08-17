#!/usr/bin/env python3
"""Build a digest-bound review artifact for later trusted jobs and the poller."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from agent_protocol.artifact import build_artifact, dump_artifact


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pr-number", required=True, type=int)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--workflow-run-id", required=True)
    parser.add_argument("--trusted-workflow-sha", required=True)
    parser.add_argument("--review-input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    payload = Path(args.review_input).read_text(encoding="utf-8")
    artifact = build_artifact(
        pr_number=args.pr_number,
        head_sha=args.head_sha,
        task=args.task,
        workflow_run_id=args.workflow_run_id,
        trusted_workflow_sha=args.trusted_workflow_sha,
        review_payload=payload,
    )
    Path(args.output).write_text(json.dumps(dump_artifact(artifact), indent=2), encoding="utf-8")
    print(artifact.digest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
