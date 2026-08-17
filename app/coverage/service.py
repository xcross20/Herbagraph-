"""Coverage service used by Discovery. In-memory catalog first."""

from __future__ import annotations

from app.coverage.evaluator import CoverageAssessment, evaluate
from app.coverage.resolver import CanonicalTestMatch, resolve_test
from app.coverage.seed import RELATIONS


class CoverageService:
    async def resolve_test(self, raw_name: str, protocol_text: str | None = None) -> CanonicalTestMatch | None:
        return resolve_test(raw_name, protocol_text)

    async def evaluate(
        self,
        test_id: str,
        investigation_concept: str,
        protocol_id: str | None = None,
    ) -> CoverageAssessment:
        return evaluate(test_id, investigation_concept, protocol_id)

    async def remaining_gaps(self, completed_workup: list[str], branches: list[str]) -> list[dict]:
        done = {item.lower() for item in completed_workup}
        gaps: list[dict] = []
        for row in RELATIONS:
            if row.concept not in branches:
                continue
            if row.relation != "directly_assesses":
                continue
            if any(row.test_code in item or row.test_code.replace("_", " ") in item for item in done):
                continue
            gaps.append(
                {
                    "concept": row.concept,
                    "test_code": row.test_code,
                    "relation": row.relation,
                    "label": f"Evaluate {row.concept.replace('_', ' ')}",
                }
            )
        return gaps[:12]
