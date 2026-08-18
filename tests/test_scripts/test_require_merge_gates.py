from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from require_merge_gates import evaluate  # noqa: E402


SHA = "4d1afadd7d60aa0431aa4be8c29893585191619b"
GREEN = [
    {"name": "gates", "conclusion": "success"},
    {"name": "postgres-truth", "conclusion": "success"},
]


def _review(status: str, sha: str = SHA, login: str | None = "xcross20") -> dict:
    item = {
        "body": (
            "HERBAGRAPH_ARCHITECT_REVIEW\n"
            f"Task: HG-37\n"
            f"Reviewed commit: {sha}\n"
            f"Status: {status}\n"
        )
    }
    if login is not None:
        item["user"] = {"login": login}
    return item


def _emergency(sha: str = SHA, login: str = "xcross20", reason: str = "recorded uat unblock") -> dict:
    return {
        "user": {"login": login},
        "body": f"HERBAGRAPH_EMERGENCY_BYPASS\nCommit: {sha}\nReason: {reason}\n",
    }


def test_merge_gates_require_exact_sha_approval_and_green_checks():
    result = evaluate(head_sha=SHA, comments=[_review("ARCHITECT_APPROVED")], reviews=[], checks=GREEN)
    assert result["ok"] is True
    assert result["actor"] == "xcross20"


def test_merge_gates_reject_stale_approval_and_red_ci():
    stale = evaluate(
        head_sha=SHA,
        comments=[_review("ARCHITECT_APPROVED", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")],
        reviews=[],
        checks=GREEN,
    )
    assert stale["ok"] is False
    red = evaluate(
        head_sha=SHA,
        comments=[_review("ARCHITECT_APPROVED")],
        reviews=[],
        checks=[{"name": "gates", "conclusion": "failure"}],
    )
    assert red["ok"] is False
    blocked = evaluate(
        head_sha=SHA,
        comments=[_review("CHANGES_REQUIRED")],
        reviews=[{"state": "CHANGES_REQUESTED", "commit_id": SHA}],
        checks=GREEN,
    )
    assert blocked["ok"] is False


def test_untrusted_author_cannot_approve():
    result = evaluate(
        head_sha=SHA,
        comments=[_review("ARCHITECT_APPROVED", login="random-commenter")],
        reviews=[],
        checks=GREEN,
    )
    assert result["ok"] is False
    assert result["reason"] == "architect_approval_untrusted_author"


def test_approval_without_login_is_rejected():
    result = evaluate(
        head_sha=SHA,
        comments=[_review("ARCHITECT_APPROVED", login=None)],
        reviews=[],
        checks=GREEN,
    )
    assert result["ok"] is False
    assert result["reason"] == "architect_approval_untrusted_author"


def test_untrusted_author_cannot_emergency_bypass():
    result = evaluate(
        head_sha=SHA,
        comments=[_emergency(login="random-commenter")],
        reviews=[],
        checks=GREEN,
    )
    assert result["ok"] is False
    assert result["reason"] == "emergency_bypass_untrusted_author"


def test_unstructured_emergency_marker_is_rejected():
    result = evaluate(
        head_sha=SHA,
        comments=[{"user": {"login": "xcross20"}, "body": f"EMERGENCY_BYPASS {SHA}"}],
        reviews=[],
        checks=GREEN,
    )
    assert result["ok"] is False
    assert result["reason"] == "missing_exact_sha_architect_approved"


def test_founder_structured_emergency_is_accepted():
    result = evaluate(head_sha=SHA, comments=[_emergency()], reviews=[], checks=GREEN)
    assert result["ok"] is True
    assert result["reason"] == "emergency_bypass"
