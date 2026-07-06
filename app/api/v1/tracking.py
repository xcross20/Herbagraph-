import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.enums import LabReportStatus
from app.models.evidence import EvidenceClaim
from app.models.intervention import Intervention
from app.models.lab import LabReport
from app.models.patient import Patient
from app.models.response_tracking import ResponseTracking
from app.models.user import User
from app.pipeline.biomarker_normalizer import normalized_results_from_lab_report
from app.pipeline.response_analysis import generate_response_report
from app.schemas.response import (
    BiologicalResponseReportRead,
    ResponseTrackingCreate,
    ResponseTrackingFollowUp,
    ResponseTrackingRead,
)

router = APIRouter(prefix="/tracking", tags=["tracking"])


async def _get_owned_lab_report(lab_report_id: uuid.UUID, current_user: User, db: AsyncSession) -> LabReport:
    result = await db.execute(
        select(LabReport).where(LabReport.id == lab_report_id, LabReport.user_id == current_user.id)
    )
    lab_report = result.scalar_one_or_none()
    if lab_report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lab report not found")
    return lab_report


async def _get_owned_tracking(tracking_id: uuid.UUID, current_user: User, db: AsyncSession) -> ResponseTracking:
    result = await db.execute(
        select(ResponseTracking).where(
            ResponseTracking.id == tracking_id, ResponseTracking.user_id == current_user.id
        )
    )
    tracking = result.scalar_one_or_none()
    if tracking is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Response tracking record not found")
    return tracking


@router.post("", response_model=ResponseTrackingRead, status_code=status.HTTP_201_CREATED)
async def create_tracking(
    payload: ResponseTrackingCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ResponseTracking:
    baseline = await _get_owned_lab_report(payload.baseline_lab_report_id, current_user, db)
    if baseline.status != LabReportStatus.COMPLETE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Baseline lab report is not ready (status={baseline.status.value})",
        )

    if payload.patient_id is not None:
        result = await db.execute(
            select(Patient).where(Patient.id == payload.patient_id, Patient.user_id == current_user.id)
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

    tracking = ResponseTracking(
        user_id=current_user.id,
        patient_id=payload.patient_id,
        intervention_name=payload.intervention_name,
        baseline_lab_report_id=payload.baseline_lab_report_id,
        started_at=payload.started_at,
    )
    db.add(tracking)
    await db.commit()
    await db.refresh(tracking)
    return tracking


@router.get("", response_model=list[ResponseTrackingRead])
async def list_tracking(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[ResponseTracking]:
    result = await db.execute(
        select(ResponseTracking)
        .where(ResponseTracking.user_id == current_user.id)
        .order_by(ResponseTracking.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/{tracking_id}", response_model=ResponseTrackingRead)
async def get_tracking(
    tracking_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ResponseTracking:
    return await _get_owned_tracking(tracking_id, current_user, db)


@router.delete("/{tracking_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tracking(
    tracking_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    tracking = await _get_owned_tracking(tracking_id, current_user, db)
    await db.delete(tracking)
    await db.commit()


@router.post("/{tracking_id}/follow-up", response_model=ResponseTrackingRead)
async def attach_follow_up(
    tracking_id: uuid.UUID,
    payload: ResponseTrackingFollowUp,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ResponseTracking:
    tracking = await _get_owned_tracking(tracking_id, current_user, db)
    if payload.follow_up_lab_report_id == tracking.baseline_lab_report_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Follow-up lab report must differ from the baseline lab report",
        )

    follow_up = await _get_owned_lab_report(payload.follow_up_lab_report_id, current_user, db)
    if follow_up.status != LabReportStatus.COMPLETE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Follow-up lab report is not ready (status={follow_up.status.value})",
        )

    tracking.follow_up_lab_report_id = follow_up.id
    await db.commit()
    await db.refresh(tracking)
    return tracking


@router.get("/{tracking_id}/response", response_model=BiologicalResponseReportRead)
async def get_response_report(
    tracking_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    tracking = await _get_owned_tracking(tracking_id, current_user, db)
    if tracking.follow_up_lab_report_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="No follow-up lab report attached yet"
        )

    baseline = await _get_owned_lab_report(tracking.baseline_lab_report_id, current_user, db)
    follow_up = await _get_owned_lab_report(tracking.follow_up_lab_report_id, current_user, db)
    await db.refresh(baseline, attribute_names=["lab_results"])
    await db.refresh(follow_up, attribute_names=["lab_results"])

    result = await db.execute(select(Intervention).where(Intervention.name == tracking.intervention_name))
    intervention = result.scalar_one_or_none()
    evidence_claims: list[EvidenceClaim] = []
    if intervention is not None:
        claims_result = await db.execute(
            select(EvidenceClaim).where(EvidenceClaim.intervention_id == intervention.id)
        )
        evidence_claims = list(claims_result.scalars().all())

    return generate_response_report(
        intervention_name=tracking.intervention_name,
        baseline_results=normalized_results_from_lab_report(baseline),
        follow_up_results=normalized_results_from_lab_report(follow_up),
        baseline_date=baseline.created_at,
        follow_up_date=follow_up.created_at,
        evidence_claims=evidence_claims,
    )
