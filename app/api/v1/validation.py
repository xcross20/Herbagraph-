import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_admin_user, get_current_user, get_db
from app.models.report import RecommendationReport
from app.models.user import User
from app.models.validation import ReportFeedback, ValidationEvent
from app.schemas.validation import (
    ReportFeedbackCreate,
    ReportFeedbackRead,
    ValidationDashboardRead,
    ValidationEventCreate,
    ValidationEventRead,
)
from app.services.validation_analytics import build_validation_dashboard, serialize_event_metadata

router = APIRouter(tags=["validation"])

_TIME_SAVED_MINUTES = {
    "under_5": 3,
    "5_10": 7,
    "10_20": 15,
    "over_20": 25,
}

_ENCOUNTER_TRUST_SCORE = {
    "yes": 5,
    "yes_minor_edits": 4,
    "background_only": 2,
    "no": 1,
}

_ENCOUNTER_WOULD_USE = {
    "yes": "yes",
    "yes_minor_edits": "yes",
    "background_only": "unsure",
    "no": "no",
}


async def _get_owned_report(report_id: uuid.UUID, current_user: User, db: AsyncSession) -> RecommendationReport:
    result = await db.execute(
        select(RecommendationReport).where(
            RecommendationReport.id == report_id,
            RecommendationReport.user_id == current_user.id,
        )
    )
    report = result.scalar_one_or_none()
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return report


@router.post("/reports/{report_id}/report-feedback", response_model=ReportFeedbackRead, status_code=status.HTTP_201_CREATED)
async def submit_report_feedback(
    report_id: uuid.UUID,
    payload: ReportFeedbackCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReportFeedback:
    report = await _get_owned_report(report_id, current_user, db)
    trust_score = _ENCOUNTER_TRUST_SCORE[payload.patient_encounter_comfort]
    would_use_again = payload.would_use_again or _ENCOUNTER_WOULD_USE[payload.patient_encounter_comfort]
    time_saved = (
        _TIME_SAVED_MINUTES[payload.estimated_time_saved_bucket]
        if payload.estimated_time_saved_bucket
        else None
    )

    feedback = ReportFeedback(
        report_id=report.id,
        user_id=current_user.id,
        clinical_usefulness_score=payload.clinical_usefulness_score,
        reasoning_agreement=payload.reasoning_agreement,
        trust_score=trust_score,
        estimated_time_saved_minutes=time_saved,
        most_useful_section=payload.most_useful_section,
        least_useful_section=payload.least_useful_section,
        patient_encounter_comfort=payload.patient_encounter_comfort,
        would_use_again=would_use_again,
        safety_concerns=payload.safety_concerns,
        free_text_feedback=payload.free_text_feedback,
    )
    db.add(feedback)

    db.add(
        ValidationEvent(
            report_id=report.id,
            user_id=current_user.id,
            event_type="submitted_feedback",
            section_name="report_feedback",
            metadata_json=serialize_event_metadata(
                {
                    "clinical_usefulness_score": payload.clinical_usefulness_score,
                    "reasoning_agreement": payload.reasoning_agreement,
                    "patient_encounter_comfort": payload.patient_encounter_comfort,
                }
            ),
        )
    )
    await db.commit()
    await db.refresh(feedback)
    return feedback


@router.post("/validation/events", response_model=ValidationEventRead, status_code=status.HTTP_201_CREATED)
async def track_validation_event(
    payload: ValidationEventCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ValidationEvent:
    if payload.report_id is not None:
        await _get_owned_report(payload.report_id, current_user, db)

    event = ValidationEvent(
        report_id=payload.report_id,
        user_id=current_user.id,
        event_type=payload.event_type,
        section_name=payload.section_name,
        metadata_json=serialize_event_metadata(payload.metadata),
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event


@router.get("/admin/validation/dashboard", response_model=ValidationDashboardRead)
async def get_validation_dashboard(
    _: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> ValidationDashboardRead:
    return await build_validation_dashboard(db)