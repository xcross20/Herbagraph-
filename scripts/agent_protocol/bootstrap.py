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


_SHA40 = __import__("re").compile(r"^[0-9a-f]{40}$")


def verify_trusted_sha(resolved_sha: str, approved_sha: str, *, is_ancestor=None) -> str:
    """Fail closed unless the resolved SHA is the approved SHA or a documented descendant."""
    resolved = (resolved_sha or "").lower()
    if not resolved or not _SHA40.match(resolved):
        raise ValueError("missing_default_branch_sha")
    approved = (approved_sha or "").lower()
    if not approved or not _SHA40.match(approved):
        raise ValueError("empty_or_invalid_bootstrap_lock")
    if resolved == approved:
        return resolved
    if is_ancestor is None:
        raise ValueError("ancestry_check_required")
    if is_ancestor(approved, resolved):
        return resolved
    raise ValueError("unapproved_orchestrator_sha")


def github_is_descendant(*, api_root: str, approved_sha: str, resolved_sha: str, request) -> bool:
    """True when resolved is identical to approved or strictly ahead of it."""
    payload = request("GET", f"{api_root}/compare/{approved_sha}...{resolved_sha}", "")
    status = str(payload.get("status") or "")
    return status in {"identical", "ahead"}
