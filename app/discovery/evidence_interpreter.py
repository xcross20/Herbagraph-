"""Turn a workup + target branches into typed evidence drafts.

Cartesian pairing is forbidden. Only explicitly proposed branch codes are
considered. `not_applicable` and unresolved labels produce no edge.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.discovery.coverage_governor import assess_coverage
from app.discovery.evidence_mapping import decide_evidence_mapping
from app.discovery.resolver import resolve_test
from app.models.enums import CoverageRelation, EvidenceRelationship, ResolverStatus, ResultState


@dataclass(frozen=True)
class EvidenceEdgeDraft:
    test_code: str
    branch_code: str
    relationship: EvidenceRelationship
    coverage: CoverageRelation
    explanation: str
    raw_label: str


@dataclass
class InterpretResult:
    edges: list[EvidenceEdgeDraft] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)
    ambiguous: list[str] = field(default_factory=list)
    discarded: list[str] = field(default_factory=list)


def interpret_workup(
    *,
    raw_label: str,
    branch_codes: list[str],
    result_state: str | ResultState | None = None,
) -> InterpretResult:
    result = InterpretResult()
    resolved = resolve_test(raw_label)
    if resolved.status is ResolverStatus.UNRESOLVED:
        result.unresolved.append(raw_label)
        return result
    if resolved.status is ResolverStatus.AMBIGUOUS:
        from app.discovery.tripwires import record_ambiguous_resolver

        record_ambiguous_resolver()
        result.ambiguous.append(raw_label)
        return result
    assert resolved.match is not None
    for branch in branch_codes:
        assessment = assess_coverage(resolved.match.code, branch)
        decision = decide_evidence_mapping(assessment.relation, result_state)
        if decision.relationship is None:
            result.discarded.append(f"{resolved.match.code}:{branch}:{decision.reason}")
            continue
        result.edges.append(
            EvidenceEdgeDraft(
                test_code=resolved.match.code,
                branch_code=branch,
                relationship=decision.relationship,
                coverage=assessment.relation,
                explanation=assessment.explanation,
                raw_label=raw_label,
            )
        )
    return result
