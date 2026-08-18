"""PHI-safe correctness tripwires. Threshold zero unless noted."""

from __future__ import annotations

from collections import Counter

from app.discovery.coverage_catalog import normalize_label
from app.discovery.telemetry import increment

ZERO_TRIPWIRES = (
    "inactive_finding_exposed_as_active",
    "multiple_active_semantic_facts",
    "correction_missing_predecessor",
    "branch_closed_without_direct_evidence",
    "unrelated_evidence_edge",
    "unknown_coverage_as_negative",
    "sourceless_scientific_output",
    "safety_escalation_lost",
    "partial_presented_as_success",
)


def evaluate_finding_projection(rows: list) -> list[str]:
    violations: list[str] = []
    active = [row for row in rows if getattr(row, "active", True)]
    seen: Counter[str] = Counter()
    for row in active:
        key = f"{normalize_label(getattr(row, 'name', ''))}"
        seen[key] += 1
        if getattr(row, "active", True) is False:
            violations.append("inactive_finding_exposed_as_active")
    for key, count in seen.items():
        if count > 1:
            violations.append("multiple_active_semantic_facts")
    for row in rows:
        if getattr(row, "supersedes_finding_id", None) is None:
            continue
        predecessor = next((item for item in rows if item.id == row.supersedes_finding_id), None)
        if predecessor is None:
            violations.append("correction_missing_predecessor")
    for name in violations:
        increment(name)
    return violations


def record_unknown_coverage() -> None:
    increment("unknown_coverage_rate")


def record_ambiguous_resolver() -> None:
    increment("ambiguous_resolver_rate")


def record_replay_converged() -> None:
    increment("duplicate_replay_converged")
