"""Attach a signed-in Stack Check to the Case the user already has.

Labs stay on LabReport. Verdicts stay on DiscoveryFinding.
There is no stack table and no second lab store.
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.discovery.authorization import require_owned_case
from app.discovery.coverage_catalog import normalize_label
from app.discovery.engine import FindingDraft
from app.discovery.mutations import apply_finding_drafts
from app.discovery.service import create_case
from app.models.discovery import DiscoveryCase, DiscoveryFinding
from app.models.enums import (
    DiscoveryCaseStatus,
    DiscoveryFindingKind,
    LabProcessingStage,
    LabReportStatus,
)
from app.models.lab import LabReport
from app.models.user import User
from app.pipeline.consumer_report import STACK_SOURCE, ref_for_verdict
from app.pipeline.manual_labs import MANUAL_PATH, normalize_typed_rows, persist_normalized
from app.pipeline.stack_verdicts import evaluate_stack

STACK_CONCERN = "Stack check"
SAVED_REPORT = "saved_report"
ENTERED_WITH_CHECK = "entered_with_check"


async def attach_stack_check(
    db: AsyncSession,
    user: User,
    *,
    labs: list[dict],
    stack: list[str],
    medications: list[str] | None,
    conditions: list[str] | None,
    case_id: uuid.UUID | None,
) -> dict:
    """Evaluate the stack against the labs that belong on the Case, then record both there."""
    case = await _open_case(db, user.id, case_id)
    report = await _report_for_case(db, user.id, case)
    if report is None:
        lab_rows = labs
        labs_source = ENTERED_WITH_CHECK
    else:
        lab_rows = [
            {"name": row.biomarker_name, "value": row.value, "unit": row.unit}
            for row in report.lab_results
        ]
        labs_source = SAVED_REPORT
    normalized = normalize_typed_rows(lab_rows)
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No numeric lab values could be read",
        )
    decision = evaluate_stack(
        labs=lab_rows,
        stack=stack,
        medications=medications,
        conditions=conditions,
    )
    if case is None:
        case = await create_case(db, user_id=user.id, presenting_concern=STACK_CONCERN)
    if labs_source == ENTERED_WITH_CHECK:
        report = await _write_manual_report(db, user.id, case.patient_id, normalized)
        case.lab_report_id = report.id
    elif case.lab_report_id is None:
        case.lab_report_id = report.id
    await apply_finding_drafts(
        db,
        case.id,
        _drafts(normalized, decision["verdicts"]),
        source_event_id=STACK_SOURCE,
    )
    await _stamp_phrase_refs(db, case.id, decision["verdicts"])
    await db.flush()
    return {
        "case": case,
        "lab_report_id": case.lab_report_id,
        "labs_source": labs_source,
        "verdicts": decision["verdicts"],
    }


async def _open_case(
    db: AsyncSession,
    user_id: uuid.UUID,
    case_id: uuid.UUID | None,
) -> DiscoveryCase | None:
    if case_id is not None:
        case = await require_owned_case(db, case_id, user_id)
        if case.status != DiscoveryCaseStatus.OPEN:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This case is closed. Start a new one.",
            )
        return case
    rows = list(
        (
            await db.execute(
                select(DiscoveryCase).where(
                    DiscoveryCase.user_id == user_id,
                    DiscoveryCase.status == DiscoveryCaseStatus.OPEN,
                )
            )
        ).scalars()
    )
    if len(rows) > 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="More than one open case. Pass case_id for the case this stack belongs to.",
        )
    if len(rows) == 1:
        return rows[0]
    return None


async def _report_for_case(
    db: AsyncSession,
    user_id: uuid.UUID,
    case: DiscoveryCase | None,
) -> LabReport | None:
    if case is not None and case.lab_report_id is not None:
        report = await _owned_report(db, user_id, case.lab_report_id)
        if report is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lab report not found")
        return report
    patient_id = case.patient_id if case is not None else None
    query = select(LabReport).where(LabReport.user_id == user_id)
    if patient_id is None:
        query = query.where(LabReport.patient_id.is_(None))
    else:
        query = query.where(LabReport.patient_id == patient_id)
    result = await db.execute(
        query.order_by(LabReport.created_at.desc()).limit(1).options(selectinload(LabReport.lab_results))
    )
    return result.scalar_one_or_none()


async def _owned_report(db: AsyncSession, user_id: uuid.UUID, report_id: uuid.UUID) -> LabReport | None:
    result = await db.execute(
        select(LabReport)
        .where(LabReport.id == report_id, LabReport.user_id == user_id)
        .options(selectinload(LabReport.lab_results))
    )
    return result.scalar_one_or_none()


async def _write_manual_report(
    db: AsyncSession,
    user_id: uuid.UUID,
    patient_id: uuid.UUID | None,
    normalized,
) -> LabReport:
    report = LabReport(
        user_id=user_id,
        patient_id=patient_id,
        original_filename="manual-entry",
        encrypted_file_path=MANUAL_PATH,
        file_size_bytes=0,
        status=LabReportStatus.COMPLETE,
        processing_stage=LabProcessingStage.COMPLETE,
    )
    db.add(report)
    await db.flush()
    await persist_normalized(db, report, normalized, replace=False)
    return report


async def _stamp_phrase_refs(db: AsyncSession, case_id: uuid.UUID, verdicts: list[dict]) -> None:
    """Keep the phrase key on the finding. The verdict code in value stays the fact."""
    rows = list(
        (
            await db.execute(select(DiscoveryFinding).where(DiscoveryFinding.case_id == case_id))
        ).scalars()
    )
    by_name = {
        normalize_label(row.name): row
        for row in rows
        if getattr(row, "active", True)
        and row.source == STACK_SOURCE
        and row.kind == DiscoveryFindingKind.CONTEXT
    }
    for verdict in verdicts:
        row = by_name.get(normalize_label(verdict["input"]))
        if row is None:
            continue
        ref = ref_for_verdict(verdict)
        row.source_event_id = f"{STACK_SOURCE}:{ref}" if ref else STACK_SOURCE


def _drafts(normalized, verdicts: list[dict]) -> list[FindingDraft]:
    drafts = [
        FindingDraft(
            kind=DiscoveryFindingKind.LAB.value,
            name=row.biomarker_name,
            value=str(row.value),
            status=row.status.value,
            branch=None,
            source=STACK_SOURCE,
        )
        for row in normalized
    ]
    drafts.extend(
        FindingDraft(
            kind=DiscoveryFindingKind.CONTEXT.value,
            name=row["input"],
            value=row["verdict"],
            status=row["verdict"],
            branch=row.get("code"),
            source=STACK_SOURCE,
        )
        for row in verdicts
    )
    return drafts
