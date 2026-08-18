"""Single coverage-to-evidence conversion boundary (ADR-MVP-002).

Coverage strings must never be stored as evidence relationships. A stub that
maps `directly_assesses` to `supports` is forbidden: interpretation is
branch-rule specific.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.models.enums import CoverageRelation, EvidenceRelationship, ResultState

MappingMetric = str
_METRICS: dict[str, int] = {
    "mapped": 0,
    "discarded_not_applicable": 0,
    "unknown_coverage": 0,
    "unrecognized_coverage": 0,
    "directly_assesses_without_rule": 0,
}


def mapping_metrics() -> dict[str, int]:
    return dict(_METRICS)


def reset_mapping_metrics() -> None:
    for key in _METRICS:
        _METRICS[key] = 0


def _count(name: str) -> None:
    _METRICS[name] = _METRICS.get(name, 0) + 1


def coerce_coverage(value: str | CoverageRelation | None) -> CoverageRelation | None:
    if value is None:
        return None
    if isinstance(value, CoverageRelation):
        return value
    blob = str(value).strip().lower()
    if not blob:
        return None
    try:
        return CoverageRelation(blob)
    except ValueError:
        return None


def coerce_result_state(value: str | ResultState | None) -> ResultState | None:
    if value is None:
        return None
    if isinstance(value, ResultState):
        return value
    blob = str(value).strip().lower()
    if not blob:
        return None
    try:
        return ResultState(blob)
    except ValueError:
        return None


BranchRule = Callable[[CoverageRelation, ResultState | None], EvidenceRelationship | None]


@dataclass(frozen=True)
class MappingDecision:
    relationship: EvidenceRelationship | None
    coverage: CoverageRelation | None
    discarded: bool
    reason: str


def coverage_to_evidence_relationship(
    coverage_relation: str | CoverageRelation | None,
    result_state: str | ResultState | None = None,
    *,
    branch_rule: BranchRule | None = None,
) -> EvidenceRelationship | None:
    """Pure mapping. Returns None when no evidence edge may be written."""
    return decide_evidence_mapping(
        coverage_relation,
        result_state,
        branch_rule=branch_rule,
    ).relationship


def decide_evidence_mapping(
    coverage_relation: str | CoverageRelation | None,
    result_state: str | ResultState | None = None,
    *,
    branch_rule: BranchRule | None = None,
) -> MappingDecision:
    coverage = coerce_coverage(coverage_relation)
    result = coerce_result_state(result_state)
    if coverage is None:
        _count("unrecognized_coverage")
        _count("unknown_coverage")
        return MappingDecision(None, None, True, "unrecognized_or_empty_coverage")
    if coverage is CoverageRelation.NOT_APPLICABLE:
        _count("discarded_not_applicable")
        return MappingDecision(None, coverage, True, "not_applicable")
    if coverage is CoverageRelation.UNKNOWN:
        _count("unknown_coverage")
        return MappingDecision(None, coverage, True, "unknown_coverage")
    if coverage is CoverageRelation.DOES_NOT_DIRECTLY_ASSESS:
        _count("mapped")
        return MappingDecision(
            EvidenceRelationship.DOES_NOT_ADDRESS,
            coverage,
            False,
            "non_addressing",
        )
    if branch_rule is not None:
        mapped = branch_rule(coverage, result)
        _count("mapped")
        return MappingDecision(mapped, coverage, mapped is None, "branch_rule")
    if coverage is CoverageRelation.PARTIALLY_ASSESSES:
        _count("mapped")
        return MappingDecision(
            EvidenceRelationship.INCONCLUSIVE,
            coverage,
            False,
            "partial_default_inconclusive",
        )
    if coverage is CoverageRelation.DIRECTLY_ASSESSES:
        if result is ResultState.POSITIVE:
            _count("mapped")
            return MappingDecision(EvidenceRelationship.SUPPORTS, coverage, False, "direct_positive")
        if result is ResultState.NEGATIVE:
            _count("mapped")
            return MappingDecision(EvidenceRelationship.WEAKENS, coverage, False, "direct_negative")
        if result is ResultState.INDETERMINATE:
            _count("mapped")
            return MappingDecision(EvidenceRelationship.INCONCLUSIVE, coverage, False, "direct_indeterminate")
    _count("directly_assesses_without_rule")
    return MappingDecision(None, coverage, True, "directly_assesses_requires_branch_rule")
