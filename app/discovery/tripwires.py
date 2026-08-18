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


def evaluate_finding_projection(canonical_rows: list, exposed: list | None = None) -> list[str]:
    """Compare the exposed projection to canonical rows.

    `exposed` is what the API/map/read returned. If omitted, the active
    canonical subset is used. Inactive resurrection is detected only when an
    exposed item matches an inactive row and no active row of that identity.
    """
    violations: list[str] = []
    canonical = list(canonical_rows)
    if exposed is None:
        exposed_rows = [row for row in canonical if getattr(row, "active", True)]
    else:
        exposed_rows = list(exposed)

    inactive = [row for row in canonical if not getattr(row, "active", True)]
    active = [row for row in canonical if getattr(row, "active", True)]
    inactive_ids = {row.id for row in inactive}

    seen: Counter[str] = Counter()
    for row in active:
        seen[normalize_label(getattr(row, "name", ""))] += 1
    for _key, count in seen.items():
        if count > 1:
            violations.append("multiple_active_semantic_facts")

    for item in exposed_rows:
        item_id = getattr(item, "id", None)
        if item_id is not None and item_id in inactive_ids:
            violations.append("inactive_finding_exposed_as_active")
            continue
        name = getattr(item, "name", None)
        value = getattr(item, "value", None)
        if item_id is None and name is not None:
            has_active = any(row.name == name and row.value == value for row in active)
            has_inactive = any(row.name == name and row.value == value for row in inactive)
            if has_inactive and not has_active:
                violations.append("inactive_finding_exposed_as_active")

    for row in canonical:
        if getattr(row, "supersedes_finding_id", None) is None:
            continue
        predecessor = next((item for item in canonical if item.id == row.supersedes_finding_id), None)
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


def record_document_classified(kind: str) -> None:
    increment(f"document_classified_{kind}")
