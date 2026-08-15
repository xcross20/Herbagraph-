"""Read-only Discovery tools. Writes go through validated mutations only."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.coverage.service import CoverageService
from app.discovery.literature import retrieve_citations
from app.discovery.snapshot import current_snapshot
from app.models.discovery import (
    DiscoveryCase,
    DiscoveryEvidenceGap,
    DiscoveryFinding,
    DiscoveryInvestigationBranch,
    DiscoveryPriorWorkupItem,
    DiscoveryTimelineEvent,
)


class DiscoveryToolbelt:
    def __init__(self, db: AsyncSession, case: DiscoveryCase):
        self.db = db
        self.case = case
        self.coverage = CoverageService()

    async def get_patient_snapshot(self) -> dict[str, Any]:
        if not self.case.patient_id:
            return {}
        row = await current_snapshot(self.db, self.case.patient_id)
        if row is None:
            return {}
        import json

        try:
            return json.loads(row.payload)
        except json.JSONDecodeError:
            return {}

    async def get_active_findings(self) -> list[dict[str, Any]]:
        rows = (
            await self.db.execute(
                select(DiscoveryFinding).where(
                    DiscoveryFinding.case_id == self.case.id,
                    DiscoveryFinding.is_active.is_(True),
                )
            )
        ).scalars()
        return [{"name": item.name, "value": item.value, "kind": item.kind.value} for item in rows]

    async def get_timeline(self) -> list[dict[str, Any]]:
        rows = (
            await self.db.execute(
                select(DiscoveryTimelineEvent).where(
                    DiscoveryTimelineEvent.case_id == self.case.id,
                    DiscoveryTimelineEvent.is_active.is_(True),
                )
            )
        ).scalars()
        return [{"label": item.label, "description": item.description} for item in rows]

    async def get_prior_workup(self) -> list[dict[str, Any]]:
        rows = (
            await self.db.execute(
                select(DiscoveryPriorWorkupItem).where(DiscoveryPriorWorkupItem.case_id == self.case.id)
            )
        ).scalars()
        return [
            {
                "test": item.raw_test_name,
                "result": item.raw_result_summary,
                "verification": item.verification_state.value,
            }
            for item in rows
        ]

    async def get_evidence_gaps(self) -> list[dict[str, Any]]:
        rows = (
            await self.db.execute(
                select(DiscoveryEvidenceGap).where(
                    DiscoveryEvidenceGap.case_id == self.case.id,
                    DiscoveryEvidenceGap.status != "resolved",
                )
            )
        ).scalars()
        return [{"code": item.code, "label": item.label, "status": item.status.value} for item in rows]

    async def get_investigation_map(self) -> list[dict[str, Any]]:
        rows = (
            await self.db.execute(
                select(DiscoveryInvestigationBranch).where(DiscoveryInvestigationBranch.case_id == self.case.id)
            )
        ).scalars()
        return [{"code": item.code, "label": item.label, "status": item.status.value} for item in rows]

    async def get_test_coverage(self, raw_name: str, concept: str) -> dict[str, Any]:
        match = await self.coverage.resolve_test(raw_name)
        if match is None:
            return {"relation": "not_applicable", "explanation": "Unknown test name."}
        assessment = await self.coverage.evaluate(match.test_code, concept, match.protocol_code)
        return {
            "relation": assessment.relation,
            "coverage_confidence": assessment.coverage_confidence,
            "explanation": assessment.explanation,
            "commercial_rank_used": False,
        }

    async def search_pubmed(self, query: str) -> list[dict]:
        if len(query or "") < 4:
            return []
        return await retrieve_citations(query)
