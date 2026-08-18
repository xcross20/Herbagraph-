"""Fail closed unless a PR may merge to integration/agent.

Required:
- head SHA has ARCHITECT_APPROVED from an allowlisted architect
- no unresolved CHANGES_REQUIRED / CHANGES_REQUESTED on that SHA
- required CI contexts are success
- emergency bypass only from an allowlisted founder with Commit + Reason
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from agent_protocol.constants import VERDICT_APPROVED, VERDICT_CHANGES_REQUIRED  # noqa: E402
from agent_protocol.parse import parse_architect_review  # noqa: E402


REQUIRED_CONTEXTS = ("gates", "postgres-truth")
EMERGENCY_MARKERS = ("HERBAGRAPH_EMERGENCY_BYPASS",)
_REASON_RE = re.compile(r"^Reason:\s*(.+)$", re.I | re.M)
_COMMIT_RE = re.compile(r"^Commit:\s*([0-9a-f]{7,40})\s*$", re.I | re.M)


def _sha(text: str) -> str:
    return (text or "").strip().lower()


def _logins(raw: str | None, default: str) -> set[str]:
    values = (raw or default).split(",")
    return {item.strip().lower() for item in values if item.strip()}


def _sha_matches(head: str, candidate: str) -> bool:
    left = _sha(candidate)
    if len(left) < 7:
        return False
    return head == left or head.startswith(left) or left.startswith(head)


def _comment_login(item: dict) -> str:
    user = item.get("user") or {}
    return str(user.get("login") or "").strip().lower()


def _parse_emergency(body: str, head: str) -> bool:
    if EMERGENCY_MARKERS[0] not in (body or ""):
        return False
    commit = _COMMIT_RE.search(body or "")
    reason = _REASON_RE.search(body or "")
    if commit is None or reason is None or not reason.group(1).strip():
        return False
    return _sha_matches(head, commit.group(1))


def evaluate(
    *,
    head_sha: str,
    comments: list[dict],
    reviews: list[dict],
    checks: list[dict],
    architect_logins: set[str] | None = None,
    founder_logins: set[str] | None = None,
) -> dict:
    head = _sha(head_sha)
    if len(head) < 40:
        return {"ok": False, "reason": "head_sha_not_full"}

    architects = architect_logins or _logins(os.environ.get("HERBAGRAPH_ARCHITECT_LOGINS"), "xcross20")
    founders = founder_logins or _logins(os.environ.get("HERBAGRAPH_FOUNDER_LOGINS"), "xcross20")

    latest_for_sha = None
    latest_login = ""
    for item in comments:
        parsed = parse_architect_review(item.get("body") or "")
        if parsed is None:
            continue
        if _sha_matches(head, parsed.reviewed_commit):
            latest_for_sha = parsed
            latest_login = _comment_login(item)

    emergency = False
    for item in comments:
        if _parse_emergency(item.get("body") or "", head):
            if _comment_login(item) not in founders:
                return {"ok": False, "reason": "emergency_bypass_untrusted_author"}
            emergency = True

    blocking_review = any(
        (item.get("state") or "").upper() == "CHANGES_REQUESTED"
        and _sha_matches(head, item.get("commit_id") or "")
        for item in reviews
    )
    if blocking_review and not emergency:
        return {"ok": False, "reason": "unresolved_changes_requested"}

    if latest_for_sha and latest_for_sha.status == VERDICT_CHANGES_REQUIRED and not emergency:
        return {"ok": False, "reason": "unresolved_architect_changes_required"}

    approved = bool(latest_for_sha and latest_for_sha.status == VERDICT_APPROVED)
    if approved and latest_login not in architects:
        return {"ok": False, "reason": "architect_approval_untrusted_author"}
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
        "actor": latest_login if approved else "founder",
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
