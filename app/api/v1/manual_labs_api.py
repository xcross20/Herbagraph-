"""Typed lab write paths. Separate module so the upload router stays file-oriented."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db, get_verified_user
from app.models.enums import AuditAction, LabProcessingStage, LabReportStatus
from app.models.lab import LabReport
from app.models.patient import Patient
from app.models.user import User
from app.pipeline.manual_labs import MANUAL_PATH, normalize_typed_rows, persist_normalized
from app.schemas.lab import LabReportRead, LabResultsPatch, ManualLabCreate
from app.services.audit import record_audit_event

router = APIRouter(prefix="/labs", tags=["labs"])


@router.post("/manual", response_model=LabReportRead, status_code=status.HTTP_201_CREATED)
async def create_manual_lab_report(
    payload: ManualLabCreate,
    request: Request,
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
) -> LabReport:
    if not payload.results:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Enter at least one lab value")
    if payload.patient_id is not None:
        patient_result = await db.execute(
            select(Patient).where(Patient.id == payload.patient_id, Patient.user_id == current_user.id)
        )
        if patient_result.scalar_one_or_none() is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

    normalized = normalize_typed_rows([row.model_dump() for row in payload.results])
    if not normalized:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No numeric lab values could be read")

    lab_report = LabReport(
        user_id=current_user.id,
        patient_id=payload.patient_id,
        original_filename="manual-entry",
        encrypted_file_path=MANUAL_PATH,
        file_size_bytes=0,
        status=LabReportStatus.COMPLETE,
        processing_stage=LabProcessingStage.COMPLETE,
    )
    db.add(lab_report)
    await db.flush()
    persist_normalized(lab_report, normalized, replace=False)
    await record_audit_event(
        db,
        action=AuditAction.LAB_UPLOADED,
        summary=f"Manual entry of {len(normalized)} biomarkers",
        user=current_user,
        patient_id=payload.patient_id,
        resource_type="lab_report",
        resource_id=str(lab_report.id),
        detail={"source": "manual", "biomarker_count": len(normalized)},
        request=request,
    )
    await db.commit()
    result = await db.execute(
        select(LabReport).options(selectinload(LabReport.lab_results)).where(LabReport.id == lab_report.id)
    )
    return result.scalar_one()


@router.patch("/{lab_report_id}/results", response_model=LabReportRead)
async def patch_lab_results(
    lab_report_id: uuid.UUID,
    payload: LabResultsPatch,
    request: Request,
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
) -> LabReport:
    result = await db.execute(
        select(LabReport)
        .options(selectinload(LabReport.lab_results))
        .where(LabReport.id == lab_report_id, LabReport.user_id == current_user.id)
    )
    lab_report = result.scalar_one_or_none()
    if lab_report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lab report not found")
    normalized = normalize_typed_rows([row.model_dump() for row in payload.results])
    if not normalized:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No numeric lab values could be read")
    persist_normalized(lab_report, normalized, replace=True)
    await record_audit_event(
        db,
        action=AuditAction.BIOMARKER_CORRECTED,
        summary=f"Corrected biomarkers on {lab_report.original_filename}",
        user=current_user,
        patient_id=lab_report.patient_id,
        resource_type="lab_report",
        resource_id=str(lab_report.id),
        detail={"biomarker_count": len(normalized)},
        request=request,
    )
    await db.commit()
    refreshed = await db.execute(
        select(LabReport).options(selectinload(LabReport.lab_results)).where(LabReport.id == lab_report.id)
    )
    return refreshed.scalar_one()
