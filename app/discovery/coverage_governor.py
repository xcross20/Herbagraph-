"""Coverage governor: canonical test × investigation concept → typed coverage."""

from __future__ import annotations

from dataclasses import dataclass

from app.discovery.coverage_catalog import RELATIONS
from app.models.enums import CoverageRelation


@dataclass(frozen=True)
class CoverageAssessment:
    relation: CoverageRelation
    explanation: str
    test_code: str
    concept: str
    protocol_code: str | None
    rule_version: str = "coverage-governor-v1"


def assess_coverage(
    test_code: str,
    investigation_concept: str,
    protocol_id: str | None = None,
) -> CoverageAssessment:
    matches = [
        row
        for row in RELATIONS
        if row.test_code == test_code and row.concept == investigation_concept
    ]
    if not matches:
        return CoverageAssessment(
            relation=CoverageRelation.NOT_APPLICABLE,
            explanation="No coverage relation is catalogued for this test and concept.",
            test_code=test_code,
            concept=investigation_concept,
            protocol_code=protocol_id,
        )
    if protocol_id:
        exact = [row for row in matches if row.protocol == protocol_id]
        if exact:
            row = exact[0]
            return CoverageAssessment(
                CoverageRelation(row.relation),
                row.explanation,
                test_code,
                investigation_concept,
                protocol_id,
            )
    generic = [row for row in matches if row.protocol is None]
    row = generic[0] if generic else matches[0]
    return CoverageAssessment(
        CoverageRelation(row.relation),
        row.explanation,
        test_code,
        investigation_concept,
        protocol_id,
    )
