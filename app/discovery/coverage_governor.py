"""Coverage governor: canonical test × investigation concept → typed coverage."""

from __future__ import annotations

from dataclasses import dataclass

from app.discovery.coverage_catalog import (
    catalog_version,
    explain_relation,
    load_catalog,
    test_name,
    concept_label,
)
from app.models.enums import CoverageRelation


@dataclass(frozen=True)
class CoverageAssessment:
    relation: CoverageRelation
    explanation: str
    test_code: str
    concept: str
    protocol_code: str | None
    rule_version: str = "coverage-catalog-v1"
    provenance: str = ""


def assess_coverage(
    test_code: str,
    investigation_concept: str,
    protocol_id: str | None = None,
) -> CoverageAssessment:
    catalog = load_catalog()
    matches = [
        row
        for row in catalog.relations
        if row.test_code == test_code and row.concept == investigation_concept
    ]
    if not matches:
        from app.discovery.tripwires import record_unknown_coverage

        record_unknown_coverage()
        return CoverageAssessment(
            relation=CoverageRelation.UNKNOWN,
            explanation=explain_relation(
                test_name=test_name(test_code),
                concept_label=concept_label(investigation_concept),
                relation=CoverageRelation.UNKNOWN.value,
            ),
            test_code=test_code,
            concept=investigation_concept,
            protocol_code=protocol_id,
            rule_version=catalog_version(),
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
                row.version,
                row.provenance,
            )
    generic = [row for row in matches if row.protocol is None]
    row = generic[0] if generic else matches[0]
    return CoverageAssessment(
        CoverageRelation(row.relation),
        row.explanation,
        test_code,
        investigation_concept,
        protocol_id,
        row.version,
        row.provenance,
    )
