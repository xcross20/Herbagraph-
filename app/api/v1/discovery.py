"""Guided Discovery Case API. The Case is the source of truth."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db, get_verified_user
from app.discovery.service import (
    create_case,
    get_owned_case,
    labs_from_ingest,
    labs_from_results,
    latest_lab_report,
    list_owned_cases,
    rebuild_case,
    snapshot_from_case,
    snapshot_to_read,
)
from app.models.lab import LabReport
from app.models.user import User
from app.schemas.discovery import DiscoveryCaseCreate, DiscoveryCaseRead, DiscoveryCaseRebuild

router = APIRouter(prefix="/cases", tags=["discovery"])


@router.get("", response_model=list[DiscoveryCaseRead])
async def list_cases(
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
) -> list[DiscoveryCaseRead]:
    cases = await list_owned_cases(db, current_user.id)
    return [snapshot_to_read(case, snapshot_from_case(case)) for case in cases]


@router.post("", response_model=DiscoveryCaseRead, status_code=status.HTTP_201_CREATED)
async def open_case(
    payload: DiscoveryCaseCreate,
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
) -> DiscoveryCaseRead:
    case = await create_case(
        db,
        user_id=current_user.id,
        presenting_concern=payload.presenting_concern,
        patient_id=payload.patient_id,
    )
    report = await latest_lab_report(db, current_user.id, payload.patient_id)
    labs = []
    lab_report_id = None
    if report is not None:
        result = await db.execute(
            select(LabReport)
            .where(LabReport.id == report.id)
            .options(selectinload(LabReport.lab_results))
        )
        report = result.scalar_one_or_none()
        if report is not None:
            labs = labs_from_results(report.lab_results)
            lab_report_id = report.id
    snapshot = await rebuild_case(db, case, labs=labs, lab_report_id=lab_report_id)
    await db.commit()
    await db.refresh(case)
    return snapshot_to_read(case, snapshot)


@router.get("/{case_id}", response_model=DiscoveryCaseRead)
async def get_case(
    case_id: uuid.UUID,
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
) -> DiscoveryCaseRead:
    case = await get_owned_case(db, case_id, current_user.id)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    return snapshot_to_read(case, snapshot_from_case(case))


@router.post("/{case_id}/rebuild", response_model=DiscoveryCaseRead)
async def rebuild_owned_case(
    case_id: uuid.UUID,
    payload: DiscoveryCaseRebuild,
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
) -> DiscoveryCaseRead:
    case = await get_owned_case(db, case_id, current_user.id)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    labs = labs_from_ingest(payload.labs) if payload.labs else None
    lab_report_id = payload.lab_report_id
    if labs is None:
        report: LabReport | None = None
        if lab_report_id is not None:
            result = await db.execute(
                select(LabReport)
                .where(LabReport.id == lab_report_id, LabReport.user_id == current_user.id)
                .options(selectinload(LabReport.lab_results))
            )
            report = result.scalar_one_or_none()
            if report is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lab report not found")
        else:
            report = await latest_lab_report(db, current_user.id, case.patient_id)
            if report is not None:
                result = await db.execute(
                    select(LabReport)
                    .where(LabReport.id == report.id)
                    .options(selectinload(LabReport.lab_results))
                )
                report = result.scalar_one_or_none()
        if report is not None:
            labs = labs_from_results(report.lab_results)
            lab_report_id = report.id

    snapshot = await rebuild_case(
        db,
        case,
        presenting_concern=payload.presenting_concern,
        labs=labs or [],
        lab_report_id=lab_report_id,
    )
    await db.commit()
    await db.refresh(case)
    return snapshot_to_read(case, snapshot)
