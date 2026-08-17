from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from require_merge_gates import evaluate  # noqa: E402


SHA = "4d1afadd7d60aa0431aa4be8c29893585191619b"


def _review(status: str, sha: str = SHA) -> dict:
    return {
        "body": (
            "HERBAGRAPH_ARCHITECT_REVIEW\n"
            f"Task: HG-37\n"
            f"Reviewed commit: {sha}\n"
            f"Status: {status}\n"
        )
    }


def test_merge_gates_require_exact_sha_approval_and_green_checks():
    result = evaluate(
        head_sha=SHA,
        comments=[_review("ARCHITECT_APPROVED")],
        reviews=[],
        checks=[
            {"name": "gates", "conclusion": "success"},
            {"name": "postgres-truth", "conclusion": "success"},
        ],
    )
    assert result["ok"] is True


def test_merge_gates_reject_stale_approval_and_red_ci():
    stale = evaluate(
        head_sha=SHA,
        comments=[_review("ARCHITECT_APPROVED", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")],
        reviews=[],
        checks=[
            {"name": "gates", "conclusion": "success"},
            {"name": "postgres-truth", "conclusion": "success"},
        ],
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
        checks=[
            {"name": "gates", "conclusion": "success"},
            {"name": "postgres-truth", "conclusion": "success"},
        ],
    )
    assert blocked["ok"] is False
