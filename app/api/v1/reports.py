import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_verified_user, get_db
from app.models.enums import AuditAction, EVIDENCE_TIER_LABELS, LabReportStatus
from app.models.feedback import Feedback
from app.models.lab import LabReport
from app.models.enums import ReportGenerationStage
from app.models.report import RecommendationReport
from app.models.user import User
from app.schemas.feedback import FeedbackCreate, FeedbackRead
from app.schemas.report import RecommendationReportRead, RecommendationReportSummary, ReportGenerationResponse
from app.services.audit import record_audit_event
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
    request: Request,
    current_user: User = Depends(get_verified_user),
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
        ReportGenerationStage.EVIDENCE_CONFIDENCE,
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

    await record_audit_event(
        db,
        action=AuditAction.ANALYSIS_STARTED,
        summary=f"Report generation started for lab {lab_report.original_filename}",
        user=current_user,
        patient_id=lab_report.patient_id,
        resource_type="lab_report",
        resource_id=str(lab_report.id),
        request=request,
    )
    await db.commit()

    task = generate_recommendation_report_task.delay(str(lab_report.id), str(current_user.id))

    return ReportGenerationResponse(
        lab_report_id=lab_report.id,
        task_id=task.id,
        report_stage=ReportGenerationStage.QUEUED,
        message="Report generation has started.",
    )


def _hydrated_supporting_literature(recommendation, citations_by_id: dict):
    from app.evidence_confidence.citations import hydrate_citation_url, hydrate_supporting_literature, lookup_citation
    from app.schemas.explainability import SupportingLiteratureEntry

    explainability = recommendation.explainability or {}
    literature = explainability.get("supporting_literature") or []
    if not literature:
        return hydrate_supporting_literature(
            recommendation.cited_study_ids or [],
            citations_by_id,
            cited_urls=recommendation.cited_urls,
        )

    cited_urls = recommendation.cited_urls or []
    hydrated: list[SupportingLiteratureEntry] = []
    for index, item in enumerate(literature):
        row = dict(item)
        if not row.get("url"):
            paired = cited_urls[index] if index < len(cited_urls) else None
            citation = lookup_citation(citations_by_id, str(row.get("study_id", "")))
            row["url"] = paired or (hydrate_citation_url(citation) if citation else None) or row.get("url")
        hydrated.append(SupportingLiteratureEntry(**row))
    return hydrated


def _hydrated_recommendation_payload(recommendation, citations_by_id: dict) -> dict:
    from app.models.enums import EVIDENCE_TIER_LABELS

    literature = _hydrated_supporting_literature(recommendation, citations_by_id)

    return {
        "rank": recommendation.rank,
        "intervention_name": recommendation.intervention_name,
        "category": recommendation.category,
        "mechanism": recommendation.mechanism,
        "evidence_level": recommendation.evidence_level,
        "evidence_tier": recommendation.evidence_tier,
        "evidence_tier_label": EVIDENCE_TIER_LABELS[recommendation.evidence_tier],
        "confidence_score": recommendation.confidence_score,
        "typical_dose": recommendation.typical_dose,
        "rationale": recommendation.rationale,
        "limitations": recommendation.limitations,
        "safety_risk": recommendation.safety_risk,
        "safety_notes": recommendation.safety_notes,
        "interactions": recommendation.interactions,
        "is_regulated": recommendation.is_regulated,
        "cited_study_ids": recommendation.cited_study_ids,
        "cited_urls": recommendation.cited_urls,
        "food_sources": recommendation.food_sources,
        "intervention_narrative": recommendation.intervention_narrative,
        "explainability": recommendation.explainability,
        "supporting_literature": literature,
    }


def _to_report_read(report: RecommendationReport) -> RecommendationReportRead:
    from app.evidence_confidence.citations import (
        build_citations_index,
        hydrate_citation_url,
    )
    from app.pipeline.report_insights import insights_from_stored_report
    from app.schemas.explainability import RecommendationExplainability

    citation_rows = [
        {
            "id": c.external_id,
            "source": c.source,
            "title": c.title,
            "year": c.year,
            "study_type": c.study_type,
            "quality_score": c.quality_score,
            "url": hydrate_citation_url(
                {
                    "id": c.external_id,
                    "source": c.source,
                    "title": c.title,
                    "year": c.year,
                    "study_type": c.study_type,
                    "quality_score": c.quality_score,
                    "url": c.url,
                }
            ),
        }
        for c in report.citations
    ]
    citations_by_id = build_citations_index(citation_rows)

    rec_dicts = [
        {
            "intervention_name": r.intervention_name,
            "evidence_tier": r.evidence_tier.value if hasattr(r.evidence_tier, "value") else r.evidence_tier,
            "confidence_score": r.confidence_score,
            "explainability": r.explainability,
        }
        for r in report.recommendations
    ]
    explainability_items = [
        RecommendationExplainability(**r.explainability)
        for r in report.recommendations
        if r.explainability
    ]
    citation_rows_for_insights = [
        {
            "id": c.external_id,
            "study_type": c.study_type,
        }
        for c in report.citations
    ]
    insights = report.report_insights or insights_from_stored_report(
        report.biomarker_summary or {},
        report.biological_systems or [],
        report.pathway_activations or [],
        rec_dicts,
        explainability_items=explainability_items or None,
        citations=citation_rows_for_insights,
    )
    full_rec_payloads = [
        _hydrated_recommendation_payload(r, citations_by_id)
        for r in report.recommendations
    ]
    recommendation_tiers = insights.get("recommendation_tiers")
    biological_hierarchy = insights.get("biological_hierarchy")
    dual_clinical_rankings = insights.get("dual_clinical_rankings")
    clinical_summary_hero = insights.get("clinical_summary_hero")
    if not recommendation_tiers or not biological_hierarchy or not dual_clinical_rankings:
        from app.pipeline.evidence_retriever import build_intervention_pathway_map
        from app.pipeline.report_biological_hierarchy import build_biological_hierarchy
        from app.pipeline.report_clinical_priorities import build_dual_clinical_rankings
        from app.pipeline.report_tiering import build_recommendation_tiers

        intervention_pathways = build_intervention_pathway_map()
        if not recommendation_tiers:
            recommendation_tiers = build_recommendation_tiers(
                full_rec_payloads,
                report.biomarker_summary or {},
                insights.get("biological_systems") or report.biological_systems or [],
                executive_summary=report.executive_summary or "",
                intervention_pathways=intervention_pathways,
                pathway_activations=report.pathway_activations or [],
            )
            insights["recommendation_tiers"] = recommendation_tiers
        if not biological_hierarchy:
            biological_hierarchy = build_biological_hierarchy(
                report.biomarker_summary or {},
                insights.get("biological_systems") or report.biological_systems or [],
                report.pathway_activations or [],
                full_rec_payloads,
                intervention_pathways,
            )
            insights["biological_hierarchy"] = biological_hierarchy
        if not dual_clinical_rankings:
            dual_clinical_rankings = build_dual_clinical_rankings(
                report.biomarker_summary or {},
                insights.get("biological_systems") or report.biological_systems or [],
                report.pathway_activations or [],
                full_rec_payloads,
                intervention_pathways,
            )
            insights["dual_clinical_rankings"] = dual_clinical_rankings
    if not clinical_summary_hero and dual_clinical_rankings:
        from app.pipeline.report_clinical_summary import build_clinical_summary_hero

        clinical_summary_hero = build_clinical_summary_hero(
            dual_clinical_rankings,
            insights.get("overall_confidence_assessment"),
            report.biomarker_summary or {},
        )
        insights["clinical_summary_hero"] = clinical_summary_hero
    if not insights.get("report_methodology"):
        from app.pipeline.report_methodology import build_report_methodology

        insights["report_methodology"] = build_report_methodology(
            report.biomarker_summary or {},
            insights.get("biological_systems") or report.biological_systems or [],
            report.pathway_activations or [],
            rec_dicts,
            citations=citation_rows_for_insights,
        )

    return RecommendationReportRead(
        id=report.id,
        lab_report_id=report.lab_report_id,
        overall_confidence=report.overall_confidence,
        model_version=report.model_version,
        executive_summary=report.executive_summary,
        biomarker_summary=report.biomarker_summary,
        biomarker_interpretations=report.biomarker_interpretations,
        pathway_activations=report.pathway_activations,
        biological_systems=insights.get("biological_systems") or report.biological_systems,
        recommendations=[
            _hydrated_recommendation_payload(r, citations_by_id)
            for r in report.recommendations
        ],
        citations=citation_rows,
        clinician_questions=report.clinician_questions,
        safety_summary=report.safety_summary,
        medication_context=report.medication_context or {},
        lab_trends=report.lab_trends or {},
        disclaimer=report.disclaimer,
        report_versioning=report.report_versioning,
        evidence_summary=insights.get("evidence_summary"),
        missing_information=insights.get("missing_information"),
        overall_confidence_assessment=insights.get("overall_confidence_assessment"),
        biological_reasoning_summary=insights.get("biological_reasoning_summary"),
        differential_explanations=insights.get("differential_explanations"),
        patient_evidence_gaps=insights.get("patient_evidence_gaps"),
        report_methodology=insights.get("report_methodology"),
        report_insights=insights,
        recommendation_tiers=recommendation_tiers,
        biological_hierarchy=biological_hierarchy,
        dual_clinical_rankings=dual_clinical_rankings,
        clinical_summary_hero=clinical_summary_hero,
        created_at=report.created_at,
    )


@router.get("", response_model=list[RecommendationReportSummary])
async def list_reports(
    patient_id: uuid.UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[RecommendationReport]:
    query = select(RecommendationReport).where(RecommendationReport.user_id == current_user.id)
    if patient_id is not None:
        query = query.join(LabReport, RecommendationReport.lab_report_id == LabReport.id).where(
            LabReport.patient_id == patient_id
        )
    result = await db.execute(query.order_by(RecommendationReport.created_at.desc()))
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
    request: Request,
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
) -> RecommendationReportRead:
    report = await _get_owned_report(report_id, current_user, db)
    await db.refresh(report, attribute_names=["recommendations", "citations"])
    await record_audit_event(
        db,
        action=AuditAction.REPORT_VIEWED,
        summary=f"Report viewed ({report_id})",
        user=current_user,
        resource_type="report",
        resource_id=str(report_id),
        request=request,
    )
    await db.commit()
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
