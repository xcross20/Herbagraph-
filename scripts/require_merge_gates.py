"""Fail closed unless a PR may merge to integration/agent.

Required:
- head SHA has ARCHITECT_APPROVED (or documented emergency bypass)
- no unresolved CHANGES_REQUIRED / CHANGES_REQUESTED on that SHA
- required CI contexts are success

This is a GitHub check. It does not grant merge rights; branch protection must
require this check and forbid admin bypass except a recorded emergency.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from agent_protocol.constants import VERDICT_APPROVED, VERDICT_CHANGES_REQUIRED  # noqa: E402
from agent_protocol.parse import parse_architect_review  # noqa: E402


REQUIRED_CONTEXTS = ("gates", "postgres-truth")
EMERGENCY_MARKERS = ("HERBAGRAPH_EMERGENCY_BYPASS", "EMERGENCY_BYPASS")


def _sha(text: str) -> str:
    return (text or "").strip().lower()


def evaluate(*, head_sha: str, comments: list[dict], reviews: list[dict], checks: list[dict]) -> dict:
    head = _sha(head_sha)
    if len(head) < 40:
        return {"ok": False, "reason": "head_sha_not_full"}

    latest_for_sha = None
    for item in comments:
        parsed = parse_architect_review(item.get("body") or "")
        if parsed is None:
            continue
        if _sha(parsed.reviewed_commit) == head:
            latest_for_sha = parsed

    emergency = any(
        marker in (item.get("body") or "") and head in (item.get("body") or "").lower()
        for item in comments
        for marker in EMERGENCY_MARKERS
    )

    blocking_review = any(
        (item.get("state") or "").upper() == "CHANGES_REQUESTED"
        and _sha((item.get("commit_id") or "")) == head
        for item in reviews
    )
    if blocking_review and not emergency:
        return {"ok": False, "reason": "unresolved_changes_requested"}

    if latest_for_sha and latest_for_sha.status == VERDICT_CHANGES_REQUIRED and not emergency:
        return {"ok": False, "reason": "unresolved_architect_changes_required"}

    approved = bool(latest_for_sha and latest_for_sha.status == VERDICT_APPROVED)
    if not approved and not emergency:
        return {"ok": False, "reason": "missing_exact_sha_architect_approved"}

    names = {}
    for item in checks:
        name = item.get("name") or ""
        conclusion = (item.get("conclusion") or item.get("status") or "").lower()
        names[name] = conclusion
    for context in REQUIRED_CONTEXTS:
        if names.get(context) != "success":
            return {"ok": False, "reason": f"required_check_not_green:{context}"}

    return {
        "ok": True,
        "reason": "emergency_bypass" if emergency else "architect_approved_exact_sha",
        "head_sha": head,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--comments-json", required=True)
    parser.add_argument("--reviews-json", required=True)
    parser.add_argument("--checks-json", required=True)
    args = parser.parse_args()
    comments = json.loads(Path(args.comments_json).read_text())
    reviews = json.loads(Path(args.reviews_json).read_text())
    checks = json.loads(Path(args.checks_json).read_text())
    result = evaluate(head_sha=args.head_sha, comments=comments, reviews=reviews, checks=checks)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
