import mimetypes
import pathlib
import re
import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_verified_user, get_db
from app.config import settings
from app.core.background_jobs import dispatch_celery_task, save_encrypted_lab_file
from app.core.file_storage import ALLOWED_EXTENSIONS, delete_lab_file, load_lab_file, save_lab_file
from app.models.enums import AuditAction, LabProcessingStage, LabReportStatus
from app.models.lab import LabReport
from app.models.patient import Patient
from app.models.user import User
from app.services.audit import record_audit_event
from app.schemas.lab import LabReportRead, LabReportSummary, LabUploadResponse
from app.workers.tasks import process_lab_report_task

router = APIRouter(prefix="/labs", tags=["labs"])


@router.post("/upload", response_model=LabUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_lab_report(
    file: UploadFile,
    request: Request,
    patient_id: uuid.UUID | None = Form(default=None),
    current_user: User = Depends(get_verified_user),
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
    saved = save_encrypted_lab_file(save_lab_file, file_bytes, lab_report.id, lab_report.original_filename)
    lab_report.encrypted_file_path = saved.encrypted_file_path
    lab_report.encrypted_file_data = saved.encrypted_file_data
    await record_audit_event(
        db,
        action=AuditAction.LAB_UPLOADED,
        summary=f"Uploaded {lab_report.original_filename}",
        user=current_user,
        patient_id=patient_id,
        resource_type="lab_report",
        resource_id=str(lab_report.id),
        detail={"filename": lab_report.original_filename, "size_bytes": lab_report.file_size_bytes},
        request=request,
    )
    await db.commit()
    await db.refresh(lab_report)

    task = dispatch_celery_task(process_lab_report_task, str(lab_report.id))

    return LabUploadResponse(
        lab_report_id=lab_report.id,
        task_id=task.id,
        message="Lab report uploaded. Processing has started.",
        status=LabReportStatus.PROCESSING,
    )


@router.get("", response_model=list[LabReportSummary])
async def list_lab_reports(
    patient_id: uuid.UUID | None = None,
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
) -> list[LabReport]:
    query = select(LabReport).where(LabReport.user_id == current_user.id)
    if patient_id is not None:
        query = query.where(LabReport.patient_id == patient_id)
    result = await db.execute(query.order_by(LabReport.created_at.desc()))
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
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
) -> LabReport:
    lab_report = await _get_owned_lab_report(lab_report_id, current_user, db)
    await db.refresh(lab_report, attribute_names=["lab_results"])
    return lab_report


def _safe_download_filename(name: str) -> str:
    """Strip path separators / control chars for Content-Disposition."""
    base = pathlib.Path(name or "lab-upload").name
    cleaned = re.sub(r"[\r\n\"\\\\]", "_", base).strip() or "lab-upload"
    return cleaned[:200]


@router.get("/{lab_report_id}/download")
async def download_lab_file(
    lab_report_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Download the original patient-uploaded lab file (PDF/txt/csv/image)."""
    lab_report = await _get_owned_lab_report(lab_report_id, current_user, db)
    if not lab_report.encrypted_file_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Original file not stored")

    try:
        file_bytes = load_lab_file(lab_report.encrypted_file_path, lab_report.encrypted_file_data)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Original file is missing from storage",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not decrypt lab file ({type(exc).__name__})",
        ) from exc

    filename = _safe_download_filename(lab_report.original_filename)
    media_type, _ = mimetypes.guess_type(filename)
    if not media_type:
        media_type = "application/octet-stream"

    await record_audit_event(
        db,
        action=AuditAction.LAB_FILE_DOWNLOADED,
        summary=f"Downloaded original lab file {filename}",
        user=current_user,
        patient_id=lab_report.patient_id,
        resource_type="lab_report",
        resource_id=str(lab_report.id),
        detail={"filename": filename, "bytes": len(file_bytes)},
        request=request,
    )
    await db.commit()

    # RFC 5987 filename* for non-ASCII names; ASCII fallback for older browsers
    ascii_name = filename.encode("ascii", "ignore").decode("ascii") or "lab-upload"
    content_disposition = (
        f'attachment; filename="{ascii_name}"; filename*=UTF-8\'\'{quote(filename)}'
    )

    return Response(
        content=file_bytes,
        media_type=media_type,
        headers={
            "Content-Disposition": content_disposition,
            "Content-Length": str(len(file_bytes)),
            "Cache-Control": "private, no-store",
        },
    )


@router.post("/{lab_report_id}/reprocess")
async def reprocess_lab_report(
    lab_report_id: uuid.UUID,
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Re-run Stage 1–2 parse/normalize on the stored original file (no re-upload)."""
    lab_report = await _get_owned_lab_report(lab_report_id, current_user, db)
    from app.workers.tasks import process_lab_report

    result = process_lab_report(str(lab_report.id), force=True)
    if result.get("status") == "failed":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=result.get("error") or "Reprocess failed",
        )
    return {
        "lab_report_id": str(lab_report_id),
        "status": result.get("status"),
        "biomarker_count": result.get("biomarker_count", 0),
        "message": "Lab report re-parsed with the current engine.",
    }


@router.delete("/{lab_report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lab_report(
    lab_report_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a lab upload and all dependent rows (session links, reports, tracking)."""
    from sqlalchemy import delete as sa_delete, or_, update as sa_update

    from app.models.analysis_session import (
        AnalysisSession,
        AnalysisSessionLabReport,
        IntegratedBiomarkerResult,
    )
    from app.models.feedback import Feedback
    from app.models.report import Recommendation, RecommendationReport, ReportCitation
    from app.models.response_tracking import ResponseTracking
    from app.models.validation import ReportFeedback, ValidationEvent

    lab_report = await _get_owned_lab_report(lab_report_id, current_user, db)
    filename = lab_report.original_filename
    patient_id = lab_report.patient_id

    # 1) Recommendation reports that anchor this lab
    report_ids = list(
        (
            await db.execute(
                select(RecommendationReport.id).where(
                    RecommendationReport.lab_report_id == lab_report_id
                )
            )
        ).scalars().all()
    )
    if report_ids:
        await db.execute(
            sa_update(AnalysisSession)
            .where(AnalysisSession.latest_report_id.in_(report_ids))
            .values(latest_report_id=None)
        )
        await db.execute(sa_delete(Feedback).where(Feedback.report_id.in_(report_ids)))
        await db.execute(sa_delete(ReportFeedback).where(ReportFeedback.report_id.in_(report_ids)))
        await db.execute(sa_delete(ValidationEvent).where(ValidationEvent.report_id.in_(report_ids)))
        await db.execute(sa_delete(Recommendation).where(Recommendation.report_id.in_(report_ids)))
        await db.execute(sa_delete(ReportCitation).where(ReportCitation.report_id.in_(report_ids)))
        await db.execute(
            sa_delete(RecommendationReport).where(RecommendationReport.id.in_(report_ids))
        )

    # 2) Integrated analysis + session links that reference this lab
    await db.execute(
        sa_delete(IntegratedBiomarkerResult).where(
            IntegratedBiomarkerResult.source_lab_report_id == lab_report_id
        )
    )
    await db.execute(
        sa_delete(AnalysisSessionLabReport).where(
            AnalysisSessionLabReport.lab_report_id == lab_report_id
        )
    )

    # 3) Response tracking baselines / follow-ups
    await db.execute(
        sa_delete(ResponseTracking).where(
            or_(
                ResponseTracking.baseline_lab_report_id == lab_report_id,
                ResponseTracking.follow_up_lab_report_id == lab_report_id,
            )
        )
    )

    lab_report.latest_report_id = None

    if lab_report.encrypted_file_path:
        try:
            delete_lab_file(lab_report.encrypted_file_path)
        except (FileNotFoundError, OSError):
            pass

    await record_audit_event(
        db,
        action=AuditAction.LAB_UPLOADED,
        summary=f"Deleted lab file {filename}",
        user=current_user,
        patient_id=patient_id,
        resource_type="lab_report",
        resource_id=str(lab_report_id),
        detail={"filename": filename, "event": "lab_deleted"},
        request=request,
    )

    await db.delete(lab_report)
    try:
        await db.commit()
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Could not delete lab file because related data still references it. "
                f"({type(exc).__name__}: {exc})"
            ),
        ) from exc
