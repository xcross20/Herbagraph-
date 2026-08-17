"""Stale-run guard: never write if the remote PR head moved."""

from __future__ import annotations


def head_is_current(expected_sha: str, live_sha: str) -> bool:
    return (expected_sha or "").lower() == (live_sha or "").lower() and len(expected_sha or "") >= 40


def refuse_stale_write(expected_sha: str, live_sha: str) -> str | None:
    if head_is_current(expected_sha, live_sha):
        return None
    return "stale_run_remote_head_changed"
