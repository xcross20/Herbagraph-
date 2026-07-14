import pathlib
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_verified_user, get_db
from app.config import settings
from app.core.background_jobs import dispatch_celery_task, save_encrypted_lab_file
from app.core.file_storage import ALLOWED_EXTENSIONS, save_lab_file
from app.models.analysis_session import AnalysisSession, AnalysisSessionLabReport
from app.models.enums import AnalysisSessionStatus, AuditAction, LabProcessingStage, LabReportStatus
from app.models.lab import LabReport
from app.models.patient import Patient
from app.models.user import User
from app.services.audit import record_audit_event
from app.pipeline.integrated_merge import infer_panel_label
from app.schemas.analysis_session import (
    AnalysisSessionCreate,
    AnalysisSessionLinkLabsRequest,
    AnalysisSessionRead,
    AnalysisSessionRunResponse,
    IntegratedUploadResponse,
)
from app.workers.tasks import process_lab_report_task, run_integrated_analysis_task

router = APIRouter(prefix="/analysis-sessions", tags=["analysis-sessions"])


async def _get_owned_session(
    session_id: uuid.UUID, current_user: User, db: AsyncSession
) -> AnalysisSession:
    result = await db.execute(
        select(AnalysisSession)
        .where(AnalysisSession.id == session_id, AnalysisSession.user_id == current_user.id)
        .options(selectinload(AnalysisSession.lab_links).selectinload(AnalysisSessionLabReport.lab_report))
    )
    analysis_session = result.scalar_one_or_none()
    if analysis_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis session not found")
    return analysis_session


@router.get("", response_model=list[AnalysisSessionRead])
async def list_analysis_sessions(
    patient_id: uuid.UUID | None = None,
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
) -> list[AnalysisSessionRead]:
    query = (
        select(AnalysisSession)
        .where(AnalysisSession.user_id == current_user.id)
        .options(selectinload(AnalysisSession.lab_links).selectinload(AnalysisSessionLabReport.lab_report))
    )
    if patient_id is not None:
        query = query.where(AnalysisSession.patient_id == patient_id)
    result = await db.execute(query.order_by(AnalysisSession.created_at.desc()))
    return [_session_read_payload(session) for session in result.scalars().all()]


def _anchor_lab_report_id(analysis_session: AnalysisSession) -> uuid.UUID | None:
    """Lab that drives integrated report generation (latest upload in the session)."""
    candidates = [
        link
        for link in analysis_session.lab_links
        if link.lab_report is not None and link.lab_report.created_at is not None
    ]
    if not candidates:
        return analysis_session.lab_links[0].lab_report_id if analysis_session.lab_links else None
    anchor_link = max(candidates, key=lambda link: link.lab_report.created_at)
    return anchor_link.lab_report_id


def _session_read_payload(analysis_session: AnalysisSession) -> AnalysisSessionRead:
    lab_reports = []
    for link in analysis_session.lab_links:
        report = link.lab_report
        lab_reports.append(
            {
                "lab_report_id": link.lab_report_id,
                "panel_label": link.panel_label,
                "original_filename": report.original_filename if report else None,
                "status": report.status if report else None,
            }
        )
    return AnalysisSessionRead(
        id=analysis_session.id,
        patient_id=analysis_session.patient_id,
        title=analysis_session.title,
        analysis_type=analysis_session.analysis_type,
        status=analysis_session.status,
        report_confidence=analysis_session.report_confidence,
        analysis_date=analysis_session.analysis_date,
        error_message=analysis_session.error_message,
        latest_report_id=analysis_session.latest_report_id,
        anchor_lab_report_id=_anchor_lab_report_id(analysis_session),
        created_at=analysis_session.created_at,
        lab_reports=lab_reports,
    )


@router.post("", response_model=AnalysisSessionRead, status_code=status.HTTP_201_CREATED)
async def create_analysis_session(
    payload: AnalysisSessionCreate,
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
) -> AnalysisSessionRead:
    if payload.patient_id is not None:
        patient_result = await db.execute(
            select(Patient).where(Patient.id == payload.patient_id, Patient.user_id == current_user.id)
        )
        if patient_result.scalar_one_or_none() is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

    analysis_session = AnalysisSession(
        user_id=current_user.id,
        patient_id=payload.patient_id,
        title=payload.title,
        analysis_type=payload.analysis_type,
        status=AnalysisSessionStatus.PENDING,
    )
    db.add(analysis_session)
    await db.commit()
    await db.refresh(analysis_session)
    return AnalysisSessionRead(
        id=analysis_session.id,
        patient_id=analysis_session.patient_id,
        title=analysis_session.title,
        analysis_type=analysis_session.analysis_type,
        status=analysis_session.status,
        report_confidence=analysis_session.report_confidence,
        analysis_date=analysis_session.analysis_date,
        error_message=analysis_session.error_message,
        latest_report_id=analysis_session.latest_report_id,
        created_at=analysis_session.created_at,
        lab_reports=[],
    )


@router.post("/{session_id}/upload", response_model=IntegratedUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_lab_reports_to_session(
    session_id: uuid.UUID,
    files: list[UploadFile] = File(...),
    patient_id: uuid.UUID | None = Form(default=None),
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
) -> IntegratedUploadResponse:
    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one file is required.")

    analysis_session = await _get_owned_session(session_id, current_user, db)
    if analysis_session.status in {AnalysisSessionStatus.ANALYZING, AnalysisSessionStatus.MERGING}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Analysis is in progress for this session. Wait for completion or create a new session.",
        )

    effective_patient_id = patient_id or analysis_session.patient_id
    if effective_patient_id is not None:
        patient_result = await db.execute(
            select(Patient).where(Patient.id == effective_patient_id, Patient.user_id == current_user.id)
        )
        if patient_result.scalar_one_or_none() is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

    uploaded: list[dict] = []
    for upload_file in files:
        ext = pathlib.Path(upload_file.filename or "").suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type '{ext}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}",
            )

        file_bytes = await upload_file.read()
        if len(file_bytes) > settings.max_file_size_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds the {settings.max_file_size_mb}MB limit",
            )

        lab_report = LabReport(
            user_id=current_user.id,
            patient_id=effective_patient_id,
            original_filename=upload_file.filename or "upload",
            encrypted_file_path="",
            file_size_bytes=len(file_bytes),
            status=LabReportStatus.PROCESSING,
            processing_stage=LabProcessingStage.QUEUED,
        )
        db.add(lab_report)
        await db.flush()
        saved = save_encrypted_lab_file(save_lab_file, file_bytes, lab_report.id, lab_report.original_filename)
        lab_report.encrypted_file_path = saved.encrypted_file_path
        lab_report.encrypted_file_data = saved.encrypted_file_data

        panel_label = infer_panel_label(lab_report.original_filename)
        db.add(
            AnalysisSessionLabReport(
                analysis_session_id=analysis_session.id,
                lab_report_id=lab_report.id,
                panel_label=panel_label,
            )
        )
        await db.flush()

        task = dispatch_celery_task(process_lab_report_task, str(lab_report.id))
        uploaded.append(
            {
                "lab_report_id": str(lab_report.id),
                "panel_label": panel_label,
                "original_filename": lab_report.original_filename,
                "task_id": task.id,
            }
        )

    if analysis_session.status == AnalysisSessionStatus.COMPLETE:
        analysis_session.status = AnalysisSessionStatus.PENDING
        analysis_session.latest_report_id = None
        analysis_session.error_message = None

    await db.commit()
    return IntegratedUploadResponse(
        analysis_session_id=analysis_session.id,
        uploaded=uploaded,
        message=f"Uploaded {len(uploaded)} lab file(s). Parsing has started.",
    )


@router.post("/{session_id}/link-labs", response_model=AnalysisSessionRead)
async def link_existing_lab_reports(
    session_id: uuid.UUID,
    payload: AnalysisSessionLinkLabsRequest,
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
) -> AnalysisSessionRead:
    """Attach already-uploaded lab reports to a session (no file re-upload)."""
    analysis_session = await _get_owned_session(session_id, current_user, db)

    if analysis_session.status in {
        AnalysisSessionStatus.ANALYZING,
        AnalysisSessionStatus.MERGING,
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Analysis is in progress for this session.",
        )

    linked_ids = {link.lab_report_id for link in analysis_session.lab_links}
    for lab_report_id in payload.lab_report_ids:
        if lab_report_id in linked_ids:
            continue
        lab_result = await db.execute(
            select(LabReport).where(LabReport.id == lab_report_id, LabReport.user_id == current_user.id)
        )
        lab_report = lab_result.scalar_one_or_none()
        if lab_report is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Lab report {lab_report_id} not found")
        if analysis_session.patient_id and lab_report.patient_id and lab_report.patient_id != analysis_session.patient_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Lab report belongs to a different patient than this session.",
            )
        panel_label = infer_panel_label(lab_report.original_filename)
        db.add(
            AnalysisSessionLabReport(
                analysis_session_id=analysis_session.id,
                lab_report_id=lab_report.id,
                panel_label=panel_label,
            )
        )

    if analysis_session.status == AnalysisSessionStatus.COMPLETE:
        analysis_session.status = AnalysisSessionStatus.PENDING
        analysis_session.latest_report_id = None
        analysis_session.error_message = None

    await db.flush()
    await db.commit()
    result = await db.execute(
        select(AnalysisSession)
        .where(AnalysisSession.id == session_id, AnalysisSession.user_id == current_user.id)
        .options(selectinload(AnalysisSession.lab_links).selectinload(AnalysisSessionLabReport.lab_report))
        .execution_options(populate_existing=True)
    )
    refreshed = result.scalar_one()
    return _session_read_payload(refreshed)


@router.post("/{session_id}/run", response_model=AnalysisSessionRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def run_integrated_analysis(
    session_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
) -> AnalysisSessionRunResponse:
    analysis_session = await _get_owned_session(session_id, current_user, db)

    if len(analysis_session.lab_links) < 2:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Integrated analysis requires at least two lab reports in the session.",
        )

    active_statuses = {
        AnalysisSessionStatus.PARSING,
        AnalysisSessionStatus.MERGING,
        AnalysisSessionStatus.ANALYZING,
    }
    if analysis_session.status in active_statuses:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Integrated analysis is already in progress for this session.",
        )

    analysis_session.status = AnalysisSessionStatus.PENDING
    analysis_session.error_message = None
    await db.commit()

    await record_audit_event(
        db,
        action=AuditAction.ANALYSIS_STARTED,
        summary=f"Integrated analysis started ({analysis_session.title})",
        user=current_user,
        patient_id=analysis_session.patient_id,
        resource_type="analysis_session",
        resource_id=str(analysis_session.id),
        detail={"lab_count": len(analysis_session.lab_links)},
        request=request,
    )
    await db.commit()

    task = dispatch_celery_task(run_integrated_analysis_task, str(analysis_session.id), str(current_user.id))
    return AnalysisSessionRunResponse(
        analysis_session_id=analysis_session.id,
        task_id=task.id,
        status=AnalysisSessionStatus.PENDING,
        message="Integrated analysis has started.",
    )


@router.get("/{session_id}", response_model=AnalysisSessionRead)
async def get_analysis_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
) -> AnalysisSessionRead:
    analysis_session = await _get_owned_session(session_id, current_user, db)
    return _session_read_payload(analysis_session)