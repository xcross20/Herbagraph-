#!/usr/bin/env python3
"""Guarded merge to integration/agent. Never targets main or production."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from agent_protocol.commit_api import _request
from agent_protocol.constants import REQUIRED_BASE_BRANCH, REQUIRED_HEAD_PREFIX

AUTONOMOUS_UAT_PATHS = frozenset({"tests/fixtures/agent_loop_canary.txt"})
FORBIDDEN_BASES = frozenset({"main", "master", "production"})


@dataclass(frozen=True)
class PromoteDecision:
    allowed: bool
    reason: str
    label: str | None = None


def normalize_path(path: str) -> str:
    return (path or "").replace("\\", "/").lstrip("./")


def classify_changed_paths(paths: list[str] | tuple[str, ...]) -> PromoteDecision:
    cleaned = {normalize_path(path) for path in paths if normalize_path(path)}
    if not cleaned:
        return PromoteDecision(False, "no_changed_paths", "founder-decision-required")
    extra = sorted(cleaned - AUTONOMOUS_UAT_PATHS)
    if extra:
        return PromoteDecision(False, "path_not_autonomous_uat:" + ",".join(extra), "founder-decision-required")
    return PromoteDecision(True, "autonomous_uat_allowlist", "uat-ready")


def promote_is_safe(
    *,
    base_ref: str,
    head_ref: str,
    live_head_sha: str,
    reviewed_sha: str,
    paths: list[str] | tuple[str, ...],
) -> PromoteDecision:
    if (base_ref or "") in FORBIDDEN_BASES:
        return PromoteDecision(False, "base_is_production_or_main", "founder-decision-required")
    if (base_ref or "") != REQUIRED_BASE_BRANCH:
        return PromoteDecision(False, "base_must_be_integration_agent", "founder-decision-required")
    if not (head_ref or "").startswith(REQUIRED_HEAD_PREFIX):
        return PromoteDecision(False, "head_must_be_grok_branch", "founder-decision-required")
    if (live_head_sha or "").lower() != (reviewed_sha or "").lower():
        return PromoteDecision(False, "stale_run_remote_head_changed", None)
    if not live_head_sha or len(live_head_sha) != 40:
        return PromoteDecision(False, "missing_exact_sha", "founder-decision-required")
    return classify_changed_paths(paths)


def merge_into_integration_agent(
    *,
    api_root: str,
    token: str,
    pr_number: int,
    head_sha: str,
    title: str,
    request,
) -> dict:
    pr = request("GET", f"{api_root}/pulls/{int(pr_number)}", token)
    base_ref = ((pr.get("base") or {}).get("ref")) or ""
    head_ref = ((pr.get("head") or {}).get("ref")) or ""
    live = ((pr.get("head") or {}).get("sha") or "").lower()
    files_payload = request("GET", f"{api_root}/pulls/{int(pr_number)}/files?per_page=100", token)
    if not isinstance(files_payload, list):
        return {"merged": False, "reason": "files_payload_unreadable", "label": "founder-decision-required"}
    if len(files_payload) >= 100:
        return {"merged": False, "reason": "too_many_files", "label": "founder-decision-required"}
    paths = [str(item.get("filename") or "") for item in files_payload]
    decision = promote_is_safe(
        base_ref=base_ref,
        head_ref=head_ref,
        live_head_sha=live,
        reviewed_sha=head_sha,
        paths=paths,
    )
    if not decision.allowed:
        return {"merged": False, "reason": decision.reason, "label": decision.label}
    request(
        "PUT",
        f"{api_root}/pulls/{int(pr_number)}/merge",
        token,
        {
            "merge_method": "merge",
            "sha": live,
            "commit_title": title,
        },
    )
    return {"merged": True, "reason": decision.reason, "label": decision.label, "sha": live}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pr-number", required=True, type=int)
    parser.add_argument("--reviewed-sha", required=True)
    parser.add_argument("--task", default="UNKNOWN")
    parser.add_argument("--github-output", default=os.environ.get("GITHUB_OUTPUT"))
    args = parser.parse_args(argv)
    repo = os.environ.get("GITHUB_REPOSITORY") or ""
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
    if not repo or not token:
        raise SystemExit("missing_github_auth")
    result = merge_into_integration_agent(
        api_root=f"https://api.github.com/repos/{repo}",
        token=token,
        pr_number=args.pr_number,
        head_sha=args.reviewed_sha,
        title=f"merge(uat): {args.task} after exact-SHA architect approval",
        request=_request,
    )
    print(json.dumps(result, indent=2))
    if args.github_output:
        with open(args.github_output, "a", encoding="utf-8") as handle:
            handle.write(f"merged={'true' if result.get('merged') else 'false'}\n")
            handle.write(f"reason={result.get('reason') or ''}\n")
            handle.write(f"label={result.get('label') or ''}\n")
    return 0 if result.get("merged") or result.get("reason") != "missing_github_auth" else 1


if __name__ == "__main__":
    raise SystemExit(main())
