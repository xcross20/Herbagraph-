import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.enums import EVIDENCE_TIER_LABELS, LabReportStatus
from app.models.feedback import Feedback
from app.models.lab import LabReport
from app.models.report import Recommendation, RecommendationReport, ReportCitation
from app.models.user import HealthProfile, User
from app.pipeline.biomarker_normalizer import normalized_results_from_lab_report
from app.pipeline.evidence_retriever import build_intervention_pathway_map, retrieve_evidence
from app.pipeline.llm_reasoner import generate_reasoning
from app.pipeline.pathway_mapper import map_pathways
from app.pipeline.report_generator import generate_report
from app.pipeline.safety_layer import check_safety
from app.schemas.feedback import FeedbackCreate, FeedbackRead
from app.schemas.report import RecommendationReportRead, RecommendationReportSummary

router = APIRouter(prefix="/reports", tags=["reports"])


async def _get_owned_lab_report(lab_report_id: uuid.UUID, current_user: User, db: AsyncSession) -> LabReport:
    result = await db.execute(
        select(LabReport).where(LabReport.id == lab_report_id, LabReport.user_id == current_user.id)
    )
    lab_report = result.scalar_one_or_none()
    if lab_report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lab report not found")
    return lab_report


def _health_profile_dict(profile: HealthProfile | None) -> dict:
    if profile is None:
        return {}
    return {
        "age_range": profile.age_range,
        "biological_sex": profile.biological_sex,
        "health_goals": profile.health_goals,
        "current_medications": profile.current_medications,
        "current_supplements": profile.current_supplements,
        "known_conditions": profile.known_conditions,
    }


@router.post("/generate/{lab_report_id}", response_model=RecommendationReportRead, status_code=status.HTTP_201_CREATED)
async def generate_recommendation_report(
    lab_report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RecommendationReport:
    lab_report = await _get_owned_lab_report(lab_report_id, current_user, db)
    if lab_report.status != LabReportStatus.COMPLETE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Lab report is not ready for report generation (status={lab_report.status.value})",
        )

    await db.refresh(lab_report, attribute_names=["lab_results"])
    normalized = normalized_results_from_lab_report(lab_report)

    profile_result = await db.execute(select(HealthProfile).where(HealthProfile.user_id == current_user.id))
    health_profile = _health_profile_dict(profile_result.scalar_one_or_none())

    pathway_activations = map_pathways(normalized)
    evidence_snippets = await retrieve_evidence(pathway_activations)
    reasoning = await generate_reasoning(normalized, pathway_activations, evidence_snippets, health_profile)
    safety_report = check_safety(reasoning.recommendations, health_profile)
    intervention_pathways = build_intervention_pathway_map()

    payload = generate_report(
        normalized,
        pathway_activations,
        evidence_snippets,
        safety_report,
        reasoning.biomarker_pattern_analysis,
        reasoning.clinician_questions,
        intervention_pathways,
    )

    report = RecommendationReport(
        lab_report_id=lab_report.id,
        user_id=current_user.id,
        overall_confidence=payload["overall_confidence"],
        model_version=payload["model_version"],
        executive_summary=payload["executive_summary"],
        biomarker_summary=payload["biomarker_summary"],
        biomarker_interpretations=payload["biomarker_interpretations"],
        pathway_activations=payload["pathway_activations"],
        biological_systems=payload["biological_systems"],
        clinician_questions=payload["clinician_questions"],
        safety_summary=payload["safety_summary"],
        disclaimer=payload["disclaimer"],
    )
    db.add(report)
    await db.flush()

    for rec in payload["recommendations"]:
        db.add(
            Recommendation(
                report_id=report.id,
                rank=rec["rank"],
                intervention_name=rec["intervention_name"],
                category=rec["category"],
                mechanism=rec["mechanism"],
                evidence_level=rec["evidence_level"],
                evidence_tier=rec["evidence_tier"],
                confidence_score=rec["confidence_score"],
                typical_dose=rec["typical_dose"],
                rationale=rec["rationale"],
                limitations=rec["limitations"],
                safety_risk=rec["safety_risk"],
                safety_notes=rec["safety_notes"],
                interactions=rec["interactions"],
                is_regulated=rec["is_regulated"],
                cited_study_ids=rec["cited_study_ids"],
                cited_urls=rec["cited_urls"],
                food_sources=rec["food_sources"],
            )
        )

    for citation in payload["citations"]:
        db.add(
            ReportCitation(
                report_id=report.id,
                external_id=citation["id"],
                source=citation["source"],
                title=citation["title"],
                year=citation["year"],
                study_type=citation["study_type"],
                quality_score=citation["quality_score"],
            )
        )

    await db.commit()
    await db.refresh(report, attribute_names=["recommendations", "citations"])
    return _to_report_read(report)


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
