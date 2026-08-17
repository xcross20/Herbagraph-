"""Required CI conclusions. Approval is impossible while checks are not green."""

from __future__ import annotations

from dataclasses import dataclass

from .constants import REQUIRED_CHECK_CONTEXTS, VERDICT_APPROVED, VERDICT_FOUNDER


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


def required_checks_are_green(checks: list[CheckConclusion]) -> bool:
    required = [item for item in checks if item.required]
    if not required:
        return False
    return all(item.conclusion == "success" for item in required)


def coerce_verdict_for_checks(status: str, checks: list[CheckConclusion]) -> str:
    if status == VERDICT_APPROVED and not required_checks_are_green(checks):
        return VERDICT_FOUNDER
    return status
