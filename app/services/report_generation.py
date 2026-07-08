"""Background report generation (Stages 3–7) with progress updates on LabReport."""

from __future__ import annotations

import asyncio
import uuid

from sqlalchemy import select

from app import database
from app.models.enums import LabReportStatus, ReportGenerationStage
from app.models.lab import LabReport
from app.models.report import Recommendation, RecommendationReport, ReportCitation
from app.models.user import HealthProfile
from app.pipeline.biomarker_normalizer import normalized_results_from_lab_report, refresh_persisted_lab_results
from app.pipeline.evidence_retriever import build_intervention_pathway_map, retrieve_evidence
from app.pipeline.test_type_router import route_recommendation_trees
from app.pipeline.llm_reasoner import generate_reasoning
from app.pipeline.pathway_mapper import map_pathways
from app.pipeline.medication_context import build_medication_context
from app.pipeline.report_generator import generate_report
from app.pipeline.safety_layer import check_safety
from app.pipeline.trend_context import build_trend_context, prior_labs_from_results


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


def _set_report_stage(session, lab_report: LabReport, stage: ReportGenerationStage) -> None:
    lab_report.report_stage = stage
    session.commit()


async def _run_pipeline_stages(
    lab_report: LabReport,
    health_profile: dict,
    session,
    *,
    normalized_labs=None,
    integrated_analysis: dict | None = None,
    analysis_session_id: uuid.UUID | None = None,
    lab_trends_override: dict | None = None,
) -> RecommendationReport:
    custom_biomarkers = []
    profile = session.execute(
        select(HealthProfile).where(HealthProfile.user_id == lab_report.user_id)
    ).scalar_one_or_none()
    if profile is not None:
        custom_biomarkers = list(profile.custom_biomarkers or [])

    if normalized_labs is None:
        refresh_persisted_lab_results(lab_report.lab_results, custom_biomarkers=custom_biomarkers)
        session.commit()
        normalized = normalized_results_from_lab_report(lab_report, custom_biomarkers=custom_biomarkers)
    else:
        normalized = normalized_labs

    _set_report_stage(session, lab_report, ReportGenerationStage.PATHWAY_MAPPING)
    pathway_activations = map_pathways(normalized)
    routing = route_recommendation_trees(normalized, pathway_activations)

    _set_report_stage(session, lab_report, ReportGenerationStage.EVIDENCE_RETRIEVAL)
    evidence_snippets = await retrieve_evidence(
        pathway_activations, routing=routing, normalized_labs=normalized
    )

    _set_report_stage(session, lab_report, ReportGenerationStage.LLM_REASONING)
    reasoning = await generate_reasoning(
        normalized, pathway_activations, evidence_snippets, health_profile, routing=routing
    )

    _set_report_stage(session, lab_report, ReportGenerationStage.EVIDENCE_CONFIDENCE)

    _set_report_stage(session, lab_report, ReportGenerationStage.SAFETY_CHECK)
    safety_report = check_safety(reasoning.recommendations, health_profile, normalized_labs=normalized)
    intervention_pathways = build_intervention_pathway_map(routing, pathway_activations, normalized)

    _set_report_stage(session, lab_report, ReportGenerationStage.REPORT_ASSEMBLY)
    medication_context = build_medication_context(normalized, health_profile)

    if lab_trends_override is not None:
        lab_trends = lab_trends_override
    else:
        prior_report = (
            session.execute(
                select(LabReport)
                .where(LabReport.user_id == lab_report.user_id)
                .where(LabReport.id != lab_report.id)
                .where(LabReport.status == LabReportStatus.COMPLETE)
                .order_by(LabReport.created_at.desc())
                .limit(1)
            )
            .scalars()
            .first()
        )
        prior_labs = None
        prior_date = None
        if prior_report is not None:
            session.refresh(prior_report, attribute_names=["lab_results"])
            prior_labs = prior_labs_from_results(prior_report.lab_results)
            prior_date = prior_report.created_at.isoformat() if prior_report.created_at else None
        lab_trends = build_trend_context(normalized, prior_labs, prior_report_date=prior_date)

    payload = generate_report(
        normalized,
        pathway_activations,
        evidence_snippets,
        safety_report,
        reasoning.biomarker_pattern_analysis,
        reasoning.clinician_questions,
        intervention_pathways,
        medication_context=medication_context,
        lab_trends=lab_trends,
        routing=routing,
        custom_biomarkers=custom_biomarkers,
        health_profile=health_profile,
        integrated_analysis=integrated_analysis,
    )

    report = RecommendationReport(
        lab_report_id=lab_report.id,
        analysis_session_id=analysis_session_id,
        user_id=lab_report.user_id,
        overall_confidence=payload["overall_confidence"],
        model_version=payload["model_version"],
        executive_summary=payload["executive_summary"],
        biomarker_summary=payload["biomarker_summary"],
        biomarker_interpretations=payload["biomarker_interpretations"],
        pathway_activations=payload["pathway_activations"],
        biological_systems=payload["biological_systems"],
        clinician_questions=payload["clinician_questions"],
        safety_summary=payload["safety_summary"],
        medication_context=payload["medication_context"],
        lab_trends=payload["lab_trends"],
        disclaimer=payload["disclaimer"],
        report_versioning=payload.get("report_versioning"),
        report_insights=payload.get("report_insights"),
    )
    session.add(report)
    session.flush()

    for rec in payload["recommendations"]:
        session.add(
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
                intervention_narrative=rec.get("intervention_narrative"),
                explainability=rec.get("explainability"),
            )
        )

    for citation in payload["citations"]:
        session.add(
            ReportCitation(
                report_id=report.id,
                external_id=citation["id"],
                source=citation["source"],
                title=citation["title"],
                year=citation["year"],
                study_type=citation["study_type"],
                quality_score=citation["quality_score"],
                url=citation.get("url"),
            )
        )

    lab_report.latest_report_id = report.id
    lab_report.report_stage = ReportGenerationStage.COMPLETE
    lab_report.report_error_message = None
    session.commit()
    return report


async def _generate_report_async(lab_report_id: str, user_id: str) -> dict:
    session = database.get_sync_db()
    try:
        lab_report = session.get(LabReport, lab_report_id)
        if lab_report is None:
            return {"status": "failed", "error": "lab_report_not_found"}
        if str(lab_report.user_id) != user_id:
            return {"status": "failed", "error": "forbidden"}

        lab_report.report_stage = ReportGenerationStage.QUEUED
        lab_report.report_error_message = None
        session.commit()

        session.refresh(lab_report, attribute_names=["lab_results"])
        profile = session.execute(
            select(HealthProfile).where(HealthProfile.user_id == uuid.UUID(user_id))
        ).scalar_one_or_none()
        health_profile = _health_profile_dict(profile)

        report = await _run_pipeline_stages(lab_report, health_profile, session)
        return {"status": "complete", "report_id": str(report.id)}
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        lab_report = session.get(LabReport, lab_report_id)
        if lab_report is not None:
            lab_report.report_stage = ReportGenerationStage.FAILED
            lab_report.report_error_message = str(exc)
            session.commit()
        return {"status": "failed", "error": str(exc)}
    finally:
        session.close()


def run_report_generation(lab_report_id: str, user_id: str) -> dict:
    """Synchronous entry point for Celery workers (and eager in-process test runs)."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_generate_report_async(lab_report_id, user_id))

    # pytest-asyncio (and other nested-loop callers): run in a fresh thread+loop.
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(asyncio.run, _generate_report_async(lab_report_id, user_id)).result()