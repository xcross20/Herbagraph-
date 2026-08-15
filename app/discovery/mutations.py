"""Append-only Case mutations. Corrections supersede; they do not delete history."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.discovery import (
    DiscoveryBranchEvidence,
    DiscoveryCase,
    DiscoveryEvidenceGap,
    DiscoveryFinding,
    DiscoveryInvestigationBranch,
    DiscoveryPatientInterpretation,
    DiscoveryPriorWorkupItem,
    DiscoveryReasoningClaim,
    DiscoveryReasoningCorrection,
    DiscoveryTimelineEvent,
)
from app.models.enums import (
    DiscoveryBranchStatus,
    DiscoveryClaimStatus,
    DiscoveryEvidenceRelationship,
    DiscoveryFindingKind,
    DiscoveryGapStatus,
    DiscoveryProvenance,
    DiscoveryVerificationState,
    DiscoveryWorkupCompletion,
    DiscoveryWorkupResult,
)


class FindingMutation(BaseModel):
    name: str
    value: str | None = None
    kind: str = "symptom"
    raw_text: str | None = None
    source_turn_id: str | None = None


class SupersedeMutation(BaseModel):
    previous_name: str
    previous_value: str | None = None
    name: str
    value: str
    reason: str = "user correction"


class TimelineMutation(BaseModel):
    label: str
    description: str | None = None
    date_text: str | None = None
    source_turn_id: str | None = None


class WorkupMutation(BaseModel):
    raw_test_name: str
    result_summary: str | None = None
    result_state: str = DiscoveryWorkupResult.UNKNOWN_RESULT.value
    source_turn_id: str | None = None


class BranchMutation(BaseModel):
    code: str
    label: str
    category: str = "general"
    rationale: str | None = None
    operation: str = "OPEN"


class EvidenceMutation(BaseModel):
    branch_code: str
    relationship: str
    rationale: str | None = None
    finding_name: str | None = None
    workup_name: str | None = None


class GapMutation(BaseModel):
    code: str
    label: str
    branch_code: str | None = None
    description: str | None = None
    status: str = DiscoveryGapStatus.OPEN.value


class CorrectionMutation(BaseModel):
    reason: str
    original_text: str | None = None
    replacement_text: str | None = None


class MutationBatch(BaseModel):
    add_findings: list[FindingMutation] = Field(default_factory=list)
    supersede_findings: list[SupersedeMutation] = Field(default_factory=list)
    add_timeline_events: list[TimelineMutation] = Field(default_factory=list)
    add_prior_workup: list[WorkupMutation] = Field(default_factory=list)
    open_branches: list[BranchMutation] = Field(default_factory=list)
    add_branch_evidence: list[EvidenceMutation] = Field(default_factory=list)
    open_gaps: list[GapMutation] = Field(default_factory=list)
    add_corrections: list[CorrectionMutation] = Field(default_factory=list)
    add_interpretations: list[dict[str, Any]] = Field(default_factory=list)


class MutationResult(BaseModel):
    findings_added: int = 0
    findings_superseded: int = 0
    timeline_added: int = 0
    workup_added: int = 0
    branches_opened: int = 0
    gaps_opened: int = 0
    interpretations_added: int = 0
    corrections_added: int = 0


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _kind(raw: str) -> DiscoveryFindingKind:
    try:
        return DiscoveryFindingKind(raw)
    except ValueError:
        return DiscoveryFindingKind.CONTEXT


async def apply_mutation_batch(db: AsyncSession, case: DiscoveryCase, batch: MutationBatch) -> MutationResult:
    result = MutationResult()
    now = _now()
    for item in batch.add_findings:
        existing = (
            await db.execute(
                select(DiscoveryFinding).where(
                    DiscoveryFinding.case_id == case.id,
                    DiscoveryFinding.name == item.name,
                    DiscoveryFinding.value == item.value,
                    DiscoveryFinding.is_active.is_(True),
                    DiscoveryFinding.source_turn_id.is_not(None),
                )
            )
        ).scalars().first()
        if existing is not None:
            continue
        db.add(
            DiscoveryFinding(
                case_id=case.id,
                kind=_kind(item.kind),
                name=item.name[:200],
                value=item.value,
                source="guide",
                raw_text=item.raw_text,
                provenance=DiscoveryProvenance.PATIENT_REPORTED,
                verification_state=DiscoveryVerificationState.REPORTED,
                is_active=True,
            )
        )
        result.findings_added += 1
    for item in batch.supersede_findings:
        prior_rows = list(
            (
                await db.execute(
                    select(DiscoveryFinding).where(
                        DiscoveryFinding.case_id == case.id,
                        DiscoveryFinding.name == item.previous_name,
                        DiscoveryFinding.is_active.is_(True),
                    )
                )
            ).scalars()
        )
        replacement = DiscoveryFinding(
            case_id=case.id,
            kind=DiscoveryFindingKind.CONTEXT,
            name=item.name[:200],
            value=item.value,
            source="guide",
            provenance=DiscoveryProvenance.PATIENT_REPORTED,
            verification_state=DiscoveryVerificationState.CORRECTED,
            is_active=True,
            retraction_reason=item.reason,
        )
        db.add(replacement)
        await db.flush()
        for prior in prior_rows:
            prior.is_active = False
            prior.verification_state = DiscoveryVerificationState.CORRECTED
            prior.retracted_at = now
            prior.retraction_reason = item.reason
            prior.supersedes_finding_id = replacement.id
            result.findings_superseded += 1
    for item in batch.add_timeline_events:
        db.add(
            DiscoveryTimelineEvent(
                case_id=case.id,
                patient_id=case.patient_id,
                label=item.label[:240],
                description=item.description or item.date_text,
                date_precision="unknown",
                is_active=True,
            )
        )
        result.timeline_added += 1
    for item in batch.add_interpretations:
        statement = str(item.get("statement") or item.get("value") or "").strip()
        if not statement:
            continue
        db.add(
            DiscoveryPatientInterpretation(
                case_id=case.id,
                statement=statement[:800],
                normalized_concept=(item.get("concept") or None),
                is_active=True,
            )
        )
        result.interpretations_added += 1
    for item in batch.add_prior_workup:
        try:
            result_state = DiscoveryWorkupResult(item.result_state)
        except ValueError:
            result_state = DiscoveryWorkupResult.UNKNOWN_RESULT
        db.add(
            DiscoveryPriorWorkupItem(
                case_id=case.id,
                patient_id=case.patient_id,
                raw_test_name=item.raw_test_name[:200],
                raw_result_summary=item.result_summary,
                completion_state=DiscoveryWorkupCompletion.PATIENT_REPORTED_COMPLETED,
                result_state=result_state,
                verification_state=DiscoveryVerificationState.REPORTED,
            )
        )
        result.workup_added += 1
    for item in batch.open_branches:
        held = (
            await db.execute(
                select(DiscoveryInvestigationBranch).where(
                    DiscoveryInvestigationBranch.case_id == case.id,
                    DiscoveryInvestigationBranch.code == item.code,
                )
            )
        ).scalars().first()
        if held is None:
            db.add(
                DiscoveryInvestigationBranch(
                    case_id=case.id,
                    code=item.code[:80],
                    label=item.label[:200],
                    category=item.category[:40],
                    status=DiscoveryBranchStatus.NOT_EVALUATED,
                    rationale=item.rationale,
                    opened_reason=item.rationale,
                    opened_at=now,
                )
            )
            result.branches_opened += 1
        elif item.operation == "REOPEN" and held.status == DiscoveryBranchStatus.CONDITIONALLY_RESOLVED:
            held.status = DiscoveryBranchStatus.REOPENED
            held.reopened_at = now
    await db.flush()
    branches = {
        row.code: row
        for row in (
            await db.execute(
                select(DiscoveryInvestigationBranch).where(DiscoveryInvestigationBranch.case_id == case.id)
            )
        ).scalars()
    }
    for item in batch.add_branch_evidence:
        branch = branches.get(item.branch_code)
        if branch is None:
            continue
        try:
            relation = DiscoveryEvidenceRelationship(item.relationship)
        except ValueError:
            continue
        db.add(
            DiscoveryBranchEvidence(
                branch_id=branch.id,
                relationship=relation,
                rationale=item.rationale,
                is_active=True,
            )
        )
    for item in batch.open_gaps:
        db.add(
            DiscoveryEvidenceGap(
                case_id=case.id,
                branch_id=branches[item.branch_code].id if item.branch_code in branches else None,
                code=item.code[:80],
                label=item.label[:200],
                description=item.description,
                status=DiscoveryGapStatus(item.status) if item.status in {s.value for s in DiscoveryGapStatus} else DiscoveryGapStatus.OPEN,
                opened_at=now,
            )
        )
        result.gaps_opened += 1
    for item in batch.add_corrections:
        claim = DiscoveryReasoningClaim(
            case_id=case.id,
            claim_type="correction",
            claim_text=item.replacement_text or item.reason,
            status=DiscoveryClaimStatus.ACTIVE,
        )
        db.add(claim)
        await db.flush()
        db.add(
            DiscoveryReasoningCorrection(
                case_id=case.id,
                original_claim_id=claim.id,
                reason=item.reason,
            )
        )
        result.corrections_added += 1
    await db.flush()
    return result
