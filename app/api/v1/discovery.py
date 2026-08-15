"""Guided Discovery Case API. The Case is the source of truth."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db, get_verified_user
from app.discovery.service import (
    add_turn,
    answer_question,
    case_to_read,
    create_case,
    get_owned_case,
    labs_from_ingest,
    labs_from_results,
    latest_lab_report,
    list_owned_cases,
    rebuild_case,
    record_user_note,
)
from app.models.enums import DiscoveryTurnRole
from app.models.lab import LabReport
from app.models.user import User
from app.schemas.discovery import (
    DiscoveryAnswerCreate,
    DiscoveryCaseCreate,
    DiscoveryCaseRead,
    DiscoveryCaseRebuild,
    DiscoveryTurnCreate,
)

router = APIRouter(prefix="/cases", tags=["discovery"])


@router.get("", response_model=list[DiscoveryCaseRead])
async def list_cases(
    patient_id: uuid.UUID | None = None,
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
) -> list[DiscoveryCaseRead]:
    cases = await list_owned_cases(db, current_user.id, patient_id=patient_id)
    return [await case_to_read(db, case) for case in cases]


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
    await rebuild_case(db, case, labs=labs, lab_report_id=lab_report_id)
    await add_turn(
        db,
        case,
        role=DiscoveryTurnRole.USER,
        text=payload.presenting_concern.strip(),
        kind="concern",
    )
    await add_turn(
        db,
        case,
        role=DiscoveryTurnRole.SYSTEM,
        text=(
            "Case opened. Relevance is not a diagnosis. "
            "Answer the next questions or add a note — the Case stays the source of truth."
        ),
        kind="system",
    )
    await db.commit()
    return await case_to_read(db, case)


@router.get("/{case_id}", response_model=DiscoveryCaseRead)
async def get_case(
    case_id: uuid.UUID,
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
) -> DiscoveryCaseRead:
    case = await get_owned_case(db, case_id, current_user.id)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    return await case_to_read(db, case)


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

    await rebuild_case(
        db,
        case,
        presenting_concern=payload.presenting_concern,
        labs=labs or [],
        lab_report_id=lab_report_id,
    )
    await db.commit()
    return await case_to_read(db, case)


@router.post("/{case_id}/answers", response_model=DiscoveryCaseRead)
async def answer_case_question(
    case_id: uuid.UUID,
    payload: DiscoveryAnswerCreate,
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
) -> DiscoveryCaseRead:
    case = await get_owned_case(db, case_id, current_user.id)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    try:
        await answer_question(db, case, code=payload.code, answer=payload.answer, note=payload.note)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await db.commit()
    return await case_to_read(db, case)


@router.post("/{case_id}/turns", response_model=DiscoveryCaseRead)
async def add_case_turn(
    case_id: uuid.UUID,
    payload: DiscoveryTurnCreate,
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
) -> DiscoveryCaseRead:
    case = await get_owned_case(db, case_id, current_user.id)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    await record_user_note(db, case, payload.text)
    await db.commit()
    return await case_to_read(db, case)
