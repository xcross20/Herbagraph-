"""Required CI conclusions. Approval is impossible while checks are not green."""

from __future__ import annotations

from dataclasses import dataclass

from .constants import REQUIRED_CHECK_CONTEXTS, VERDICT_APPROVED, VERDICT_CHANGES_REQUIRED, VERDICT_FOUNDER


@dataclass(frozen=True)
class CheckConclusion:
    name: str
    conclusion: str
    required: bool = False


def parse_check_runs(payload: dict | list) -> list[CheckConclusion]:
    rows = payload.get("check_runs", payload) if isinstance(payload, dict) else payload
    out: list[CheckConclusion] = []
    for item in rows or []:
        name = str(item.get("name") or "")
        conclusion = str(item.get("conclusion") or item.get("status") or "unknown").lower()
        out.append(
            CheckConclusion(
                name=name,
                conclusion=conclusion,
                required=name in REQUIRED_CHECK_CONTEXTS,
            )
        )
    return out


PENDING_STATUSES = frozenset({"queued", "in_progress", "pending", "waiting", "requested", "running"})
FAILURE_STATUSES = frozenset({"failure", "failed", "cancelled", "timed_out", "action_required", "startup_failure", "stale"})
SUCCESS_STATUSES = frozenset({"success"})


def required_checks_are_green(checks: list[CheckConclusion]) -> bool:
    required = [item for item in checks if item.required]
    if not required:
        return False
    return all(item.conclusion == "success" for item in required)


def classify_required_checks(checks: list[CheckConclusion]) -> str:
    """pending | failed | success | missing. Untrusted/absent required contexts are missing."""
    required = [item for item in checks if item.required]
    if not required:
        return "missing"
    names = {item.name for item in required}
    if not REQUIRED_CHECK_CONTEXTS.issubset(names):
        return "missing"
    if any(item.conclusion in PENDING_STATUSES for item in required):
        return "pending"
    if any(item.conclusion in FAILURE_STATUSES or item.conclusion not in SUCCESS_STATUSES for item in required):
        return "failed"
    return "success"


def apply_check_gate(status: str, checks: list[CheckConclusion]) -> dict[str, str]:
    """Pending defers with no write. Failure is CHANGES_REQUIRED. Missing is founder."""
    state = classify_required_checks(checks)
    if state == "pending":
        return {"state": state, "status": status, "write": "false", "reason": "checks_pending"}
    if state == "missing":
        return {"state": state, "status": VERDICT_FOUNDER, "write": "true", "reason": "required_checks_missing"}
    if state == "failed":
        return {
            "state": state,
            "status": VERDICT_CHANGES_REQUIRED,
            "write": "true",
            "reason": "required_checks_failed",
        }
    return {"state": state, "status": status, "write": "true", "reason": "required_checks_green"}


def coerce_verdict_for_checks(status: str, checks: list[CheckConclusion]) -> str:
    gate = apply_check_gate(status, checks)
    if gate["state"] == "pending":
        return status
    return gate["status"]
