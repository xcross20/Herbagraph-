"""Background report generation (Stages 3–7) with progress updates on LabReport."""

from __future__ import annotations

import asyncio
import uuid

from sqlalchemy import select

from app import database
from app.models.enums import AuditAction, LabReportStatus, ReportGenerationStage
from app.services.audit import record_audit_event_sync
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
from app.services.patient_memory import build_patient_memory


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
    patient_id: uuid.UUID | None = None,
    knowledge_path: str = "legacy",
) -> RecommendationReport:
    from app.models.enums import KnowledgePath
    from app.pipeline.canonical_graph import build_interventions_for_canonical_path
    from app.pipeline.knowledge_path import parse_knowledge_path

    path = parse_knowledge_path(knowledge_path)
    memory = build_patient_memory(session, patient_id, lab_report.user_id)
    merged_profile = {**health_profile, **memory.get("patient_context", {})}
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
    knowledge_meta: dict = {"knowledge_path": path.value}
    pathway_to_interventions = None
    graph_extra_snippets: list = []
    if path == KnowledgePath.CANONICAL:
        from app.pipeline.graph_recommendation_engine import (
            build_interventions_from_graph,
            collect_best_hits,
            graph_hits_to_evidence_snippets,
        )

        pathway_to_interventions, knowledge_meta = build_interventions_from_graph(
            session, routing, pathway_activations, normalized, hybrid_legacy_fill=True
        )
        # If graph has no pathway nodes yet, fall back to registry-filtered legacy
        if knowledge_meta.get("graph_hits", 0) == 0:
            from app.pipeline.canonical_graph import build_interventions_for_canonical_path

            pathway_to_interventions, legacy_meta = build_interventions_for_canonical_path(
                routing, pathway_activations, normalized, session
            )
            knowledge_meta = {**knowledge_meta, **legacy_meta, "engine": "canonical_filter_fallback"}
        else:
            best_hits = collect_best_hits(session, pathway_activations)
            graph_extra_snippets = graph_hits_to_evidence_snippets(
                best_hits, pathway_to_interventions
            )
            knowledge_meta["graph_snippet_count"] = len(graph_extra_snippets)

    evidence_snippets = await retrieve_evidence(
        pathway_activations,
        routing=routing,
        normalized_labs=normalized,
        pathway_to_interventions=pathway_to_interventions,
    )
    if graph_extra_snippets:
        # Prefer graph snippets first for ranking; retrieve_evidence already ranks quality
        evidence_snippets = [*graph_extra_snippets, *evidence_snippets]

    _set_report_stage(session, lab_report, ReportGenerationStage.LLM_REASONING)
    reasoning = await generate_reasoning(
        normalized, pathway_activations, evidence_snippets, merged_profile, routing=routing
    )

    _set_report_stage(session, lab_report, ReportGenerationStage.EVIDENCE_CONFIDENCE)

    _set_report_stage(session, lab_report, ReportGenerationStage.SAFETY_CHECK)
    safety_report = check_safety(reasoning.recommendations, merged_profile, normalized_labs=normalized)
    if path == KnowledgePath.CANONICAL and pathway_to_interventions is not None:
        intervention_pathways = {
            name: [code for code, names in pathway_to_interventions.items() if name in names]
            for name in {n for names in pathway_to_interventions.values() for n in names}
        }
    else:
        intervention_pathways = build_intervention_pathway_map(routing, pathway_activations, normalized)

    _set_report_stage(session, lab_report, ReportGenerationStage.REPORT_ASSEMBLY)
    medication_context = build_medication_context(normalized, merged_profile)

    if lab_trends_override is not None:
        lab_trends = lab_trends_override
    else:
        prior_query = (
            select(LabReport)
            .where(LabReport.user_id == lab_report.user_id)
            .where(LabReport.id != lab_report.id)
            .where(LabReport.status == LabReportStatus.COMPLETE)
        )
        if lab_report.patient_id is not None:
            prior_query = prior_query.where(LabReport.patient_id == lab_report.patient_id)
        prior_report = session.execute(prior_query.order_by(LabReport.created_at.desc()).limit(1)).scalars().first()
        prior_labs = None
        prior_date = None
        if prior_report is not None:
            session.refresh(prior_report, attribute_names=["lab_results"])
            prior_labs = prior_labs_from_results(prior_report.lab_results)
            prior_date = prior_report.created_at.isoformat() if prior_report.created_at else None
        lab_trends = build_trend_context(normalized, prior_labs, prior_report_date=prior_date)

    graph_food_map: dict[str, list[dict]] = {}
    try:
        from app.pipeline.canonical_graph import composition_food_sources

        for rec in safety_report.approved_recommendations:
            rows = composition_food_sources(session, rec.intervention_name)
            if rows:
                # Graph CONTAINS yields compounds for foods; invert display for food_sources
                # by treating targets as linked compound foods when intervention is a compound.
                graph_food_map[rec.intervention_name] = [
                    {
                        "food_name": r.get("food_name"),
                        "richness": r.get("richness") or "moderate",
                        "typical_serving": r.get("typical_serving"),
                        "source": "canonical_graph",
                    }
                    for r in rows
                ]
    except Exception:  # noqa: BLE001 — graph food sources are best-effort
        graph_food_map = {}

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
        health_profile=merged_profile,
        integrated_analysis=integrated_analysis,
        graph_food_sources_by_intervention=graph_food_map,
    )
    insights = payload.get("report_insights") or {}
    insights["knowledge_path"] = path.value
    insights["knowledge_path_meta"] = knowledge_meta
    payload["report_insights"] = insights
    payload["model_version"] = f"{payload['model_version']}-{path.value}"

    report = RecommendationReport(
        lab_report_id=lab_report.id,
        analysis_session_id=analysis_session_id,
        user_id=lab_report.user_id,
        overall_confidence=payload["overall_confidence"],
        model_version=payload["model_version"],
        knowledge_path=path.value,
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
    record_audit_event_sync(
        session,
        action=AuditAction.REPORT_GENERATED,
        summary=f"Report generated (confidence {report.overall_confidence:.0%})",
        user_id=lab_report.user_id,
        patient_id=patient_id or lab_report.patient_id,
        resource_type="report",
        resource_id=str(report.id),
        detail={
            "overall_confidence": report.overall_confidence,
            "lab_report_id": str(lab_report.id),
            "knowledge_path": report.knowledge_path,
        },
    )
    session.commit()
    return report


async def _generate_report_async(
    lab_report_id: str, user_id: str, knowledge_path: str = "legacy"
) -> dict:
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

        report = await _run_pipeline_stages(
            lab_report,
            health_profile,
            session,
            patient_id=lab_report.patient_id,
            knowledge_path=knowledge_path,
        )
        return {
            "status": "complete",
            "report_id": str(report.id),
            "knowledge_path": report.knowledge_path,
        }
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


def run_report_generation(
    lab_report_id: str, user_id: str, knowledge_path: str = "legacy"
) -> dict:
    """Synchronous entry point for Celery workers (and eager in-process test runs)."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_generate_report_async(lab_report_id, user_id, knowledge_path))

    # pytest-asyncio (and other nested-loop callers): run in a fresh thread+loop.
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(
            asyncio.run, _generate_report_async(lab_report_id, user_id, knowledge_path)
        ).result()