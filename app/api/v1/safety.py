"""Safety Engine v1.0 API — read-only graph + dry-run evaluation."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user
from app.models.user import User
from app.safety_engine.condition_catalog import CONDITION_CATALOG
from app.safety_engine.engine import evaluate_from_input
from app.safety_engine.graph_seed import SAFETY_GRAPH_EDGES
from app.safety_engine.medication_catalog import MEDICATION_CATALOG
from app.models.enums import EvidenceLevel, InterventionCategory
from app.schemas.pipeline import LLMRecommendation
from app.schemas.safety import (
    InterventionSafetyEvaluateResponse,
    MedicationRead,
    SafetyConditionRead,
    SafetyEngineInput,
    SafetyGraphEdgeRead,
)

router = APIRouter(prefix="/safety", tags=["safety"])


@router.get("/medications", response_model=list[MedicationRead])
async def list_medications(_user: User = Depends(get_current_user)) -> list[MedicationRead]:
    return [
        MedicationRead(name=name, drug_class=meta.get("drug_class"), aliases=meta.get("aliases", []))
        for name, meta in sorted(MEDICATION_CATALOG.items())
    ]


@router.get("/conditions", response_model=list[SafetyConditionRead])
async def list_conditions(_user: User = Depends(get_current_user)) -> list[SafetyConditionRead]:
    return [
        SafetyConditionRead(key=key, label=meta["label"])
        for key, meta in sorted(CONDITION_CATALOG.items())
    ]


@router.get("/graph/edges", response_model=list[SafetyGraphEdgeRead])
async def list_graph_edges(_user: User = Depends(get_current_user)) -> list[SafetyGraphEdgeRead]:
    return [
        SafetyGraphEdgeRead(
            intervention=edge["intervention"],
            relationship=edge["relationship"],
            target=edge["target"],
            severity=edge["severity"],
            mechanism=edge["mechanism"],
            evidence_level=edge.get("evidence_level"),
            citations=list(edge.get("citations") or []),
        )
        for edge in SAFETY_GRAPH_EDGES
    ]


@router.post("/evaluate", response_model=list[InterventionSafetyEvaluateResponse])
async def evaluate_interventions(
    payload: SafetyEngineInput,
    _user: User = Depends(get_current_user),
) -> list[InterventionSafetyEvaluateResponse]:
    """Dry-run safety evaluation for integrators — does not persist a report."""
    if not payload.recommendations:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No recommendations provided")
    report = evaluate_from_input(payload)
    return [
        InterventionSafetyEvaluateResponse(
            intervention_name=rec.intervention_name,
            safety_profile=rec.safety_profile,
        )
        for rec in report.approved_recommendations
        if rec.safety_profile is not None
    ]


@router.get("/interventions/{intervention_name}", response_model=InterventionSafetyEvaluateResponse)
async def get_intervention_safety_profile(
    intervention_name: str,
    _user: User = Depends(get_current_user),
) -> InterventionSafetyEvaluateResponse:
    """Static safety profile for one intervention (no patient context)."""
    dummy = LLMRecommendation(
        intervention_name=intervention_name,
        category=InterventionCategory.HERB,
        mechanism="",
        evidence_level=EvidenceLevel.MODERATE,
    )
    report = evaluate_from_input(SafetyEngineInput(recommendations=[dummy]))
    if not report.approved_recommendations or report.approved_recommendations[0].safety_profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Intervention not found in safety graph")
    rec = report.approved_recommendations[0]
    return InterventionSafetyEvaluateResponse(
        intervention_name=rec.intervention_name,
        safety_profile=rec.safety_profile,
    )