"""Guided Discovery Case API. The Case is the source of truth."""

from __future__ import annotations

import asyncio
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db, get_verified_user
from app.discovery.service import (
    add_case_tests_to_plan,
    apply_opening_turn,
    apply_user_turn,
    answer_question,
    case_to_read,
    create_case,
    get_owned_case,
    ingest_case_document,
    labs_from_ingest,
    labs_from_results,
    latest_lab_report,
    list_owned_cases,
    list_test_plan,
    rebuild_case,
    suggested_test_labels,
    snapshot_from_case,
)
from app.models.enums import UserRole
from app.models.lab import LabReport
from app.models.user import User
from app.models.discovery import DiscoveryMapVersion, DiscoveryTurn
from app.schemas.discovery import (
    DiscoveryAnswerCreate,
    DiscoveryCaseCreate,
    DiscoveryCaseRead,
    DiscoveryCaseRebuild,
    DiscoveryDocumentCreate,
    DiscoveryDocumentRead,
    DiscoveryTestPlanCreate,
    DiscoveryTestPlanItemRead,
    DiscoveryTurnCreate,
    DiscoveryTurnRead,
)

router = APIRouter(prefix="/cases", tags=["discovery"])


def _ndjson_stream(work):
    async def events():
        queue: asyncio.Queue = asyncio.Queue()

        async def on_phase(phase: str, label: str) -> None:
            await queue.put({"event": "thinking", "phase": phase, "label": label})

        async def run() -> None:
            try:
                await work(queue.put, on_phase)
            except Exception as exc:
                await queue.put({"event": "error", "detail": str(exc)})
            finally:
                await queue.put(None)

        task = asyncio.create_task(run())
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield json.dumps(jsonable_encoder(item)) + "\n"
        finally:
            await task

    return StreamingResponse(events(), media_type="application/x-ndjson")


@router.get("", response_model=list[DiscoveryCaseRead])
async def list_cases(
    patient_id: uuid.UUID | None = None,
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
) -> list[DiscoveryCaseRead]:
    cases = await list_owned_cases(db, current_user.id, patient_id=patient_id)
    return [await case_to_read(db, case) for case in cases]


@router.get("/plan", response_model=list[DiscoveryTestPlanItemRead])
async def get_testing_plan(
    patient_id: uuid.UUID | None = None,
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
) -> list[DiscoveryTestPlanItemRead]:
    rows = await list_test_plan(db, current_user.id, patient_id=patient_id)
    return [
        DiscoveryTestPlanItemRead(
            id=row.id,
            case_id=row.case_id,
            patient_id=row.patient_id,
            label=row.label,
            reason=row.reason,
            status=row.status,
            source=row.source,
            created_at=row.created_at,
        )
        for row in rows
    ]


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
    audience = "clinician" if current_user.role in {UserRole.CLINICIAN, UserRole.ADMIN, UserRole.ORGANIZATION_ADMIN} else "consumer"
    await apply_opening_turn(db, case, payload.presenting_concern, audience=audience)
    await db.commit()
    return await case_to_read(db, case)


@router.post("/stream")
async def stream_open_case(
    payload: DiscoveryCaseCreate,
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    async def work(put, on_phase) -> None:
        await put({"event": "accepted", "text": payload.presenting_concern})
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
            loaded = await db.execute(
                select(LabReport)
                .where(LabReport.id == report.id)
                .options(selectinload(LabReport.lab_results))
            )
            report = loaded.scalar_one_or_none()
            if report is not None:
                labs = labs_from_results(report.lab_results)
                lab_report_id = report.id
        await rebuild_case(db, case, labs=labs, lab_report_id=lab_report_id)
        audience = (
            "clinician"
            if current_user.role in {UserRole.CLINICIAN, UserRole.ADMIN, UserRole.ORGANIZATION_ADMIN}
            else "consumer"
        )
        await apply_opening_turn(db, case, payload.presenting_concern, audience=audience, on_phase=on_phase)
        await db.commit()
        await put({"event": "done", "case": await case_to_read(db, case)})

    return _ndjson_stream(work)


@router.get("/{case_id}/turns", response_model=list[DiscoveryTurnRead])
async def list_case_turns(
    case_id: uuid.UUID,
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
) -> list[DiscoveryTurnRead]:
    case = await get_owned_case(db, case_id, current_user.id)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    rows = (
        await db.execute(select(DiscoveryTurn).where(DiscoveryTurn.case_id == case.id))
    ).scalars().all()
    return [
        DiscoveryTurnRead(
            id=row.id,
            role=row.role,
            text=row.text,
            kind=row.kind,
            question_code=row.question_code,
            created_at=row.created_at,
        )
        for row in sorted(rows, key=lambda item: item.created_at)
    ]


@router.get("/{case_id}/investigation-map")
async def get_investigation_map(
    case_id: uuid.UUID,
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    case = await get_owned_case(db, case_id, current_user.id)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    latest = (
        await db.execute(
            select(DiscoveryMapVersion)
            .where(DiscoveryMapVersion.case_id == case.id)
            .order_by(DiscoveryMapVersion.version.desc())
        )
    ).scalars().first()
    if latest is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investigation map not found")
    return {
        "case_id": str(case.id),
        "version": latest.version,
        "not_disease_probability": True,
        **json.loads(latest.payload),
    }


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
    audience = "clinician" if current_user.role in {UserRole.CLINICIAN, UserRole.ADMIN, UserRole.ORGANIZATION_ADMIN} else "consumer"
    await apply_user_turn(db, case, payload.text, audience=audience)
    await db.commit()
    return await case_to_read(db, case)


@router.post("/{case_id}/turns/stream")
async def stream_case_turn(
    case_id: uuid.UUID,
    payload: DiscoveryTurnCreate,
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    async def work(put, on_phase) -> None:
        await put({"event": "accepted", "text": payload.text})
        case = await get_owned_case(db, case_id, current_user.id)
        if case is None:
            await put({"event": "error", "detail": "Case not found"})
            return
        audience = (
            "clinician"
            if current_user.role in {UserRole.CLINICIAN, UserRole.ADMIN, UserRole.ORGANIZATION_ADMIN}
            else "consumer"
        )
        await apply_user_turn(db, case, payload.text, audience=audience, on_phase=on_phase)
        await db.commit()
        await put({"event": "done", "case": await case_to_read(db, case)})

    return _ndjson_stream(work)


@router.post("/{case_id}/testing-plan", response_model=list[DiscoveryTestPlanItemRead])
async def add_recommended_tests(
    case_id: uuid.UUID,
    payload: DiscoveryTestPlanCreate,
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
) -> list[DiscoveryTestPlanItemRead]:
    case = await get_owned_case(db, case_id, current_user.id)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    created = await add_case_tests_to_plan(db, case, current_user.id, payload.labels or None)
    if not created and not payload.labels:
        snapshot = snapshot_from_case(case)
        if not suggested_test_labels(snapshot):
            await db.commit()
            return []
    await db.commit()
    rows = await list_test_plan(db, current_user.id, patient_id=case.patient_id)
    return [
        DiscoveryTestPlanItemRead(
            id=row.id,
            case_id=row.case_id,
            patient_id=row.patient_id,
            label=row.label,
            reason=row.reason,
            status=row.status,
            source=row.source,
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.post("/{case_id}/documents", response_model=DiscoveryDocumentRead)
async def attach_case_document(
    case_id: uuid.UUID,
    payload: DiscoveryDocumentCreate,
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
) -> DiscoveryDocumentRead:
    case = await get_owned_case(db, case_id, current_user.id)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    result = await ingest_case_document(db, case, filename=payload.filename, text=payload.text)
    if not result["accepted"]:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=result["detail"])
    await db.commit()
    return DiscoveryDocumentRead(
        kind=result["kind"],
        accepted=True,
        detail=result["detail"],
        case=await case_to_read(db, case),
    )
