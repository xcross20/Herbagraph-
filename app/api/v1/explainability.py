"""Evidence Confidence & Explainability API — dry-run and read paths."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.evidence_confidence.engine import build_explainability_bundle
from app.models.enums import EvidenceLevel, InterventionCategory, LabResultStatus
from app.models.report import RecommendationReport
from app.models.user import User
from app.schemas.explainability import ExplainabilityEvaluateInput, ExplainabilityEvaluateResponse
from app.schemas.pipeline import EvidenceSnippet, LLMRecommendation, NormalizedLabResult, PathwayActivation

router = APIRouter(prefix="/explainability", tags=["explainability"])


def _parse_evaluate_input(payload: ExplainabilityEvaluateInput) -> tuple[
    list[LLMRecommendation],
    list[EvidenceSnippet],
    list[PathwayActivation],
    dict[str, list[str]],
    list[NormalizedLabResult],
]:
    recommendations = [
        LLMRecommendation(
            intervention_name=r["intervention_name"],
            category=InterventionCategory(r["category"]),
            mechanism=r.get("mechanism", ""),
            evidence_level=EvidenceLevel(r.get("evidence_level", "moderate")),
            typical_dose=r.get("typical_dose"),
            cited_study_ids=r.get("cited_study_ids", []),
            rationale=r.get("rationale"),
            limitations=r.get("limitations"),
        )
        for r in payload.recommendations
    ]
    evidence = [EvidenceSnippet(**e) for e in payload.evidence_snippets]
    pathways = [PathwayActivation(**p) for p in payload.pathway_activations]
    labs = [
        NormalizedLabResult(
            biomarker_name=lab["biomarker_name"],
            raw_test_name=lab.get("raw_test_name", lab["biomarker_name"]),
            value=float(lab.get("value", 0)),
            unit=lab.get("unit"),
            status=LabResultStatus(lab.get("status", "normal")),
            category=lab.get("category"),
        )
        for lab in payload.normalized_labs
    ]
    return recommendations, evidence, pathways, payload.intervention_pathways, labs


@router.post("/evaluate", response_model=ExplainabilityEvaluateResponse)
async def evaluate_explainability(
    payload: ExplainabilityEvaluateInput,
    _user: User = Depends(get_current_user),
) -> ExplainabilityEvaluateResponse:
    """Dry-run explainability for integrators — does not persist a report."""
    if not payload.recommendations:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No recommendations provided")
    recs, evidence, pathways, intervention_pathways, labs = _parse_evaluate_input(payload)
    items, versioning = build_explainability_bundle(
        recs, evidence, pathways, intervention_pathways, labs, payload.health_profile
    )
    return ExplainabilityEvaluateResponse(explainability=items, versioning=versioning)


@router.get("/reports/{report_id}", response_model=ExplainabilityEvaluateResponse)
async def get_report_explainability(
    report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExplainabilityEvaluateResponse:
    result = await db.execute(
        select(RecommendationReport).where(
            RecommendationReport.id == report_id,
            RecommendationReport.user_id == current_user.id,
        )
    )
    report = result.scalar_one_or_none()
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    await db.refresh(report, attribute_names=["recommendations"])
    from app.schemas.explainability import RecommendationExplainability, ReportVersioning

    items = []
    for rec in report.recommendations:
        if rec.explainability:
            items.append(RecommendationExplainability(**rec.explainability))
    versioning = ReportVersioning(**report.report_versioning) if report.report_versioning else None
    if versioning is None:
        from app.evidence_confidence.engine import build_report_versioning

        versioning = build_report_versioning()
    return ExplainabilityEvaluateResponse(explainability=items, versioning=versioning)