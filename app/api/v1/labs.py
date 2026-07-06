import pathlib
import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.config import settings
from app.core.file_storage import ALLOWED_EXTENSIONS, delete_lab_file, save_lab_file
from app.models.enums import LabProcessingStage, LabReportStatus
from app.models.lab import LabReport
from app.models.patient import Patient
from app.models.user import User
from app.schemas.lab import LabReportRead, LabReportSummary, LabUploadResponse
from app.workers.tasks import process_lab_report_task

router = APIRouter(prefix="/labs", tags=["labs"])


@router.post("/upload", response_model=LabUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_lab_report(
    file: UploadFile,
    patient_id: uuid.UUID | None = Form(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LabUploadResponse:
    """`patient_id` is optional and only used in clinic mode, when a clinician User
    uploads on behalf of one of their own Patients (see app/models/patient.py).
    Individual self-service users omit it entirely -- the report belongs directly
    to their own account exactly as before this field was added."""
    ext = pathlib.Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{ext}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}",
        )

    if patient_id is not None:
        patient_result = await db.execute(
            select(Patient).where(Patient.id == patient_id, Patient.user_id == current_user.id)
        )
        if patient_result.scalar_one_or_none() is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

    file_bytes = await file.read()
    if len(file_bytes) > settings.max_file_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the {settings.max_file_size_mb}MB limit",
        )

    lab_report = LabReport(
        user_id=current_user.id,
        patient_id=patient_id,
        original_filename=file.filename or "upload",
        encrypted_file_path="",
        file_size_bytes=len(file_bytes),
        status=LabReportStatus.PROCESSING,
        processing_stage=LabProcessingStage.QUEUED,
    )
    db.add(lab_report)
    await db.flush()  # assign lab_report.id before persisting the encrypted file to disk
    lab_report.encrypted_file_path = save_lab_file(file_bytes, lab_report.id, lab_report.original_filename)
    await db.commit()
    await db.refresh(lab_report)

    task = process_lab_report_task.delay(str(lab_report.id))

    return LabUploadResponse(
        lab_report_id=lab_report.id,
        task_id=task.id,
        message="Lab report uploaded. Processing has started.",
        status=LabReportStatus.PROCESSING,
    )


@router.get("", response_model=list[LabReportSummary])
async def list_lab_reports(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[LabReport]:
    result = await db.execute(
        select(LabReport).where(LabReport.user_id == current_user.id).order_by(LabReport.created_at.desc())
    )
    return list(result.scalars().all())


async def _get_owned_lab_report(lab_report_id: uuid.UUID, current_user: User, db: AsyncSession) -> LabReport:
    result = await db.execute(
        select(LabReport).where(LabReport.id == lab_report_id, LabReport.user_id == current_user.id)
    )
    lab_report = result.scalar_one_or_none()
    if lab_report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lab report not found")
    return lab_report


@router.get("/{lab_report_id}", response_model=LabReportRead)
async def get_lab_report(
    lab_report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LabReport:
    lab_report = await _get_owned_lab_report(lab_report_id, current_user, db)
    await db.refresh(lab_report, attribute_names=["lab_results"])
    return lab_report


@router.delete("/{lab_report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lab_report(
    lab_report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    lab_report = await _get_owned_lab_report(lab_report_id, current_user, db)
    if lab_report.encrypted_file_path:
        try:
            delete_lab_file(lab_report.encrypted_file_path)
        except (FileNotFoundError, OSError):
            pass
    await db.delete(lab_report)
    await db.commit()
