"""Batched UAT digest. Traceability only; never a merge/deploy action."""

from __future__ import annotations

from dataclasses import dataclass

REQUIRED_DIGEST_FIELDS = (
    "issue",
    "pr",
    "sha",
    "risk_tier",
    "rollback",
    "tests",
    "uat_url",
    "deployment_state",
    "status",
)


@dataclass(frozen=True)
class UatDigestEntry:
    issue: str
    pr: str
    sha: str
    risk_tier: str
    rollback: str
    tests: str
    uat_url: str
    deployment_state: str
    status: str


def validate_entry(entry: UatDigestEntry) -> list[str]:
    missing = []
    for field in REQUIRED_DIGEST_FIELDS:
        value = getattr(entry, field)
        if not str(value or "").strip():
            missing.append(field)
    if entry.sha and len(entry.sha) != 40:
        missing.append("sha_not_full")
    return missing


def render_digest(entries: list[UatDigestEntry]) -> str:
    lines = ["# UAT digest", ""]
    for item in entries:
        missing = validate_entry(item)
        if missing:
            raise ValueError("incomplete_digest:" + ",".join(missing))
        lines.extend(
            [
                f"## {item.issue} / {item.pr}",
                f"- SHA: `{item.sha}`",
                f"- Risk: {item.risk_tier}",
                f"- Tests: {item.tests}",
                f"- Rollback: {item.rollback}",
                f"- UAT: {item.uat_url} ({item.deployment_state})",
                f"- Status: {item.status}",
                "",
            ]
        )
    return "\n".join(lines)
