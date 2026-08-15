"""Evaluate whether a test addresses an investigation concept."""

from __future__ import annotations

from dataclasses import dataclass

from app.coverage.seed import RELATIONS


@dataclass(frozen=True)
class CoverageAssessment:
    relation: str
    coverage_confidence: float
    explanation: str
    test_code: str
    concept: str
    protocol_code: str | None


def evaluate(test_code: str, investigation_concept: str, protocol_id: str | None = None) -> CoverageAssessment:
    matches = [
        row
        for row in RELATIONS
        if row.test_code == test_code and row.concept == investigation_concept
    ]
    if not matches:
        return CoverageAssessment(
            relation="not_applicable",
            coverage_confidence=0.4,
            explanation="No coverage relation is catalogued for this test and concept.",
            test_code=test_code,
            concept=investigation_concept,
            protocol_code=protocol_id,
        )
    if protocol_id:
        exact = [row for row in matches if row.protocol == protocol_id]
        if exact:
            row = exact[0]
            return CoverageAssessment(row.relation, row.strength, row.explanation, test_code, investigation_concept, protocol_id)
    generic = [row for row in matches if row.protocol is None]
    row = generic[0] if generic else matches[0]
    confidence = row.strength if row.protocol is None or protocol_id else min(row.strength, 0.55)
    explanation = row.explanation
    if protocol_id is None and any(item.protocol for item in matches):
        explanation += " Coverage confidence is limited because the protocol is unknown."
        confidence = min(confidence, 0.62)
    return CoverageAssessment(row.relation, confidence, explanation, test_code, investigation_concept, protocol_id)
