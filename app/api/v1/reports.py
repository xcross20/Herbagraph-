import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.enums import EVIDENCE_TIER_LABELS, LabReportStatus
from app.models.feedback import Feedback
from app.models.lab import LabReport
from app.models.enums import ReportGenerationStage
from app.models.report import RecommendationReport
from app.models.user import User
from app.schemas.feedback import FeedbackCreate, FeedbackRead
from app.schemas.report import RecommendationReportRead, RecommendationReportSummary, ReportGenerationResponse
from app.workers.tasks import generate_recommendation_report_task

router = APIRouter(prefix="/reports", tags=["reports"])


async def _get_owned_lab_report(lab_report_id: uuid.UUID, current_user: User, db: AsyncSession) -> LabReport:
    result = await db.execute(
        select(LabReport).where(LabReport.id == lab_report_id, LabReport.user_id == current_user.id)
    )
    lab_report = result.scalar_one_or_none()
    if lab_report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lab report not found")
    return lab_report


@router.post(
    "/generate/{lab_report_id}",
    response_model=ReportGenerationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def generate_recommendation_report(
    lab_report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReportGenerationResponse:
    lab_report = await _get_owned_lab_report(lab_report_id, current_user, db)
    if lab_report.status != LabReportStatus.COMPLETE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Lab report is not ready for report generation (status={lab_report.status.value})",
        )

    await db.refresh(lab_report, attribute_names=["lab_results"])
    if not lab_report.lab_results:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Lab report has no parsed biomarkers. Re-upload the file or wait for processing to finish.",
        )

    active_stages = {
        ReportGenerationStage.QUEUED,
        ReportGenerationStage.PATHWAY_MAPPING,
        ReportGenerationStage.EVIDENCE_RETRIEVAL,
        ReportGenerationStage.LLM_REASONING,
        ReportGenerationStage.SAFETY_CHECK,
        ReportGenerationStage.REPORT_ASSEMBLY,
    }
    if lab_report.report_stage in active_stages:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Report generation is already in progress for this lab report",
        )

    lab_report.report_stage = ReportGenerationStage.QUEUED
    lab_report.report_error_message = None
    await db.commit()

    task = generate_recommendation_report_task.delay(str(lab_report.id), str(current_user.id))

    return ReportGenerationResponse(
        lab_report_id=lab_report.id,
        task_id=task.id,
        report_stage=ReportGenerationStage.QUEUED,
        message="Report generation has started.",
    )


def _to_report_read(report: RecommendationReport) -> RecommendationReportRead:
    return RecommendationReportRead(
        id=report.id,
        lab_report_id=report.lab_report_id,
        overall_confidence=report.overall_confidence,
        model_version=report.model_version,
        executive_summary=report.executive_summary,
        biomarker_summary=report.biomarker_summary,
        biomarker_interpretations=report.biomarker_interpretations,
        pathway_activations=report.pathway_activations,
        biological_systems=report.biological_systems,
        recommendations=[
            {
                "rank": r.rank,
                "intervention_name": r.intervention_name,
                "category": r.category,
                "mechanism": r.mechanism,
                "evidence_level": r.evidence_level,
                "evidence_tier": r.evidence_tier,
                "evidence_tier_label": EVIDENCE_TIER_LABELS[r.evidence_tier],
                "confidence_score": r.confidence_score,
                "typical_dose": r.typical_dose,
                "rationale": r.rationale,
                "limitations": r.limitations,
                "safety_risk": r.safety_risk,
                "safety_notes": r.safety_notes,
                "interactions": r.interactions,
                "is_regulated": r.is_regulated,
                "cited_study_ids": r.cited_study_ids,
                "cited_urls": r.cited_urls,
                "food_sources": r.food_sources,
                "intervention_narrative": r.intervention_narrative,
            }
            for r in report.recommendations
        ],
        citations=[
            {
                "id": c.external_id,
                "source": c.source,
                "title": c.title,
                "year": c.year,
                "study_type": c.study_type,
                "quality_score": c.quality_score,
            }
            for c in report.citations
        ],
        clinician_questions=report.clinician_questions,
        safety_summary=report.safety_summary,
        medication_context=report.medication_context or {},
        lab_trends=report.lab_trends or {},
        disclaimer=report.disclaimer,
        created_at=report.created_at,
    )


@router.get("", response_model=list[RecommendationReportSummary])
async def list_reports(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[RecommendationReport]:
    result = await db.execute(
        select(RecommendationReport)
        .where(RecommendationReport.user_id == current_user.id)
        .order_by(RecommendationReport.created_at.desc())
    )
    return list(result.scalars().all())


async def _get_owned_report(report_id: uuid.UUID, current_user: User, db: AsyncSession) -> RecommendationReport:
    result = await db.execute(
        select(RecommendationReport).where(
            RecommendationReport.id == report_id, RecommendationReport.user_id == current_user.id
        )
    )
    report = result.scalar_one_or_none()
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return report


@router.get("/{report_id}", response_model=RecommendationReportRead)
async def get_report(
    report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RecommendationReportRead:
    report = await _get_owned_report(report_id, current_user, db)
    await db.refresh(report, attribute_names=["recommendations", "citations"])
    return _to_report_read(report)


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_report(
    report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    report = await _get_owned_report(report_id, current_user, db)
    await db.delete(report)
    await db.commit()


@router.post("/{report_id}/feedback", response_model=FeedbackRead, status_code=status.HTTP_201_CREATED)
async def submit_feedback(
    report_id: uuid.UUID,
    payload: FeedbackCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Feedback:
    report = await _get_owned_report(report_id, current_user, db)
    feedback = Feedback(
        report_id=report.id, user_id=current_user.id, rating=payload.rating, comment=payload.comment
    )
    db.add(feedback)
    await db.commit()
    await db.refresh(feedback)
    return feedback


@router.get("/{report_id}/feedback", response_model=list[FeedbackRead])
async def list_feedback(
    report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Feedback]:
    report = await _get_owned_report(report_id, current_user, db)
    result = await db.execute(
        select(Feedback).where(Feedback.report_id == report.id).order_by(Feedback.created_at.desc())
    )
    return list(result.scalars().all())
