"""Persist Case snapshots. Engine stays pure; this layer owns the database."""

from __future__ import annotations

import json
import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.discovery.engine import CaseSnapshot, rebuild_case_state
from app.models.discovery import DiscoveryCase, DiscoveryFinding, DiscoveryHypothesis
from app.models.enums import (
    DiscoveryCaseStatus,
    DiscoveryFindingKind,
    DiscoveryHypothesisStatus,
)
from app.models.lab import LabReport, LabResult
from app.models.user import HealthProfile
from app.schemas.discovery import (
    BranchCoverageRead,
    DiscoveryCaseRead,
    DiscoveryFindingRead,
    DiscoveryHypothesisRead,
    DiscoveryInvestigationRead,
    LabIngest,
)
from app.schemas.pipeline import NormalizedLabResult


def labs_from_ingest(rows: list[LabIngest]) -> list[NormalizedLabResult]:
    return [
        NormalizedLabResult(
            biomarker_name=row.biomarker_name,
            raw_test_name=row.biomarker_name,
            value=row.value,
            unit=row.unit,
            status=row.status,
            category=None,
        )
        for row in rows
    ]


def labs_from_results(rows: list[LabResult]) -> list[NormalizedLabResult]:
    return [
        NormalizedLabResult(
            biomarker_name=row.biomarker_name,
            raw_test_name=row.raw_test_name or row.biomarker_name,
            value=row.value,
            unit=row.unit,
            status=row.status,
            category=None,
        )
        for row in rows
    ]


def _percent(score: float) -> int:
    return int(round(max(0.0, min(1.0, score)) * 100))


def snapshot_to_read(case: DiscoveryCase, snapshot: CaseSnapshot) -> DiscoveryCaseRead:
    return DiscoveryCaseRead(
        id=case.id,
        presenting_concern=case.presenting_concern,
        status=case.status,
        patient_id=case.patient_id,
        lab_report_id=case.lab_report_id,
        investigation_coverage=snapshot.investigation_coverage,
        investigation_coverage_percent=_percent(snapshot.investigation_coverage),
        findings=[
            DiscoveryFindingRead(
                kind=item.kind,
                name=item.name,
                value=item.value,
                status=item.status,
                source=item.source,
            )
            for item in snapshot.findings
        ],
        hypotheses=[
            DiscoveryHypothesisRead(
                code=item.code,
                label=item.label,
                branch=item.branch,
                status=item.status,
                investigation_relevance=item.investigation_relevance,
                diagnostic_certainty=item.diagnostic_certainty,
                investigation_coverage=item.investigation_coverage,
                investigation_relevance_percent=_percent(item.investigation_relevance),
                diagnostic_certainty_percent=_percent(item.diagnostic_certainty),
                investigation_coverage_percent=_percent(item.investigation_coverage),
                why_limited=item.why_limited,
                missing_markers=item.missing_markers,
                investigations=[
                    DiscoveryInvestigationRead(
                        label=inv.label,
                        group=inv.group,
                        already_assessed=inv.already_assessed,
                    )
                    for inv in item.investigations
                ],
                not_a_diagnosis=item.not_a_diagnosis,
            )
            for item in snapshot.hypotheses
        ],
        branch_coverage=[
            BranchCoverageRead(
                branch=row.branch,
                label=row.label,
                coverage=row.coverage,
                coverage_percent=_percent(row.coverage),
                assessed=row.assessed,
                expected=row.expected,
            )
            for row in snapshot.branch_coverage
        ],
        disclaimer=snapshot.disclaimer,
        created_at=case.created_at,
        updated_at=case.updated_at,
    )


async def apply_snapshot(db: AsyncSession, case: DiscoveryCase, snapshot: CaseSnapshot) -> None:
    case.presenting_concern = snapshot.presenting_concern
    case.investigation_coverage = snapshot.investigation_coverage
    case.snapshot = json.dumps(snapshot.as_dict())
    if case.id is not None:
        await db.execute(delete(DiscoveryFinding).where(DiscoveryFinding.case_id == case.id))
        await db.execute(delete(DiscoveryHypothesis).where(DiscoveryHypothesis.case_id == case.id))
        await db.flush()
    for item in snapshot.findings:
        db.add(
            DiscoveryFinding(
                case_id=case.id,
                kind=DiscoveryFindingKind(item.kind),
                name=item.name,
                value=item.value,
                status=item.status,
                branch=item.branch,
                source=item.source,
            )
        )
    for item in snapshot.hypotheses:
        db.add(
            DiscoveryHypothesis(
                case_id=case.id,
                code=item.code,
                label=item.label,
                branch=item.branch,
                status=DiscoveryHypothesisStatus.OPEN,
                investigation_relevance=item.investigation_relevance,
                diagnostic_certainty=item.diagnostic_certainty,
                investigation_coverage=item.investigation_coverage,
                rationale="; ".join(item.why_limited),
                missing_markers=json.dumps(item.missing_markers),
                investigations=json.dumps([inv.__dict__ for inv in item.investigations]),
            )
        )


async def _profile_for_user(db: AsyncSession, user_id: uuid.UUID) -> dict:
    result = await db.execute(select(HealthProfile).where(HealthProfile.user_id == user_id))
    profile = result.scalar_one_or_none()
    if profile is None:
        return {}
    return {
        "age_range": profile.age_range,
        "biological_sex": profile.biological_sex,
        "current_medications": profile.current_medications or [],
        "known_conditions": profile.known_conditions or [],
        "current_supplements": profile.current_supplements or [],
        "health_goals": profile.health_goals or [],
    }


async def latest_lab_report(db: AsyncSession, user_id: uuid.UUID, patient_id: uuid.UUID | None) -> LabReport | None:
    query = select(LabReport).where(LabReport.user_id == user_id).order_by(LabReport.created_at.desc())
    if patient_id is not None:
        query = query.where(LabReport.patient_id == patient_id)
    result = await db.execute(query.limit(1))
    return result.scalar_one_or_none()


async def create_case(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    presenting_concern: str,
    patient_id: uuid.UUID | None = None,
) -> DiscoveryCase:
    case = DiscoveryCase(
        user_id=user_id,
        patient_id=patient_id,
        presenting_concern=presenting_concern.strip(),
        status=DiscoveryCaseStatus.OPEN,
    )
    db.add(case)
    await db.flush()
    return case


async def get_owned_case(db: AsyncSession, case_id: uuid.UUID, user_id: uuid.UUID) -> DiscoveryCase | None:
    result = await db.execute(
        select(DiscoveryCase)
        .where(DiscoveryCase.id == case_id, DiscoveryCase.user_id == user_id)
        .options(selectinload(DiscoveryCase.findings), selectinload(DiscoveryCase.hypotheses))
    )
    return result.scalar_one_or_none()


async def list_owned_cases(db: AsyncSession, user_id: uuid.UUID) -> list[DiscoveryCase]:
    result = await db.execute(
        select(DiscoveryCase)
        .where(DiscoveryCase.user_id == user_id)
        .options(selectinload(DiscoveryCase.findings), selectinload(DiscoveryCase.hypotheses))
        .order_by(DiscoveryCase.updated_at.desc())
    )
    return list(result.scalars().all())


async def rebuild_case(
    db: AsyncSession,
    case: DiscoveryCase,
    *,
    presenting_concern: str | None = None,
    labs: list[NormalizedLabResult] | None = None,
    lab_report_id: uuid.UUID | None = None,
) -> CaseSnapshot:
    if presenting_concern is not None and presenting_concern.strip():
        case.presenting_concern = presenting_concern.strip()
    if lab_report_id is not None:
        case.lab_report_id = lab_report_id
    profile = await _profile_for_user(db, case.user_id)
    snapshot = rebuild_case_state(case.presenting_concern, labs or [], profile)
    await apply_snapshot(db, case, snapshot)
    await db.flush()
    return snapshot


def snapshot_from_case(case: DiscoveryCase) -> CaseSnapshot:
    if case.snapshot:
        return CaseSnapshot.from_dict(json.loads(case.snapshot))
    return rebuild_case_state(case.presenting_concern, [], {})
