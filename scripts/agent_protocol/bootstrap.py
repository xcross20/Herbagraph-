"""Pin trusted orchestration to one resolved default-branch SHA."""

from __future__ import annotations

from pathlib import Path

LOCK_RELPATH = ".github/agent-loop.lock"


def read_approved_bootstrap_sha(repo_root: Path) -> str:
    lock = repo_root / LOCK_RELPATH
    if not lock.is_file():
        return ""
    for line in lock.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.lower().startswith("approved_bootstrap_sha="):
            return stripped.split("=", 1)[1].strip().lower()
    return ""


def verify_trusted_sha(resolved_sha: str, approved_sha: str, *, is_ancestor=None) -> str:
    """Accept the resolved default-branch SHA if it is the lock SHA or a descendant."""
    resolved = (resolved_sha or "").lower()
    if not resolved:
        raise ValueError("missing_default_branch_sha")
    approved = (approved_sha or "").lower()
    if not approved:
        return resolved
    if resolved == approved:
        return resolved
    if is_ancestor is not None and is_ancestor(approved, resolved):
        return resolved
    raise ValueError("unapproved_orchestrator_sha")
