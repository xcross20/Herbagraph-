"""Safety Engine v1.0 API and pipeline schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.enums import SafetyRelationshipType, SafetyRiskLevel, SafetyWarningEvidenceLevel
from app.schemas.pipeline import LLMRecommendation, NormalizedLabResult
from app.schemas.safety_profile import InterventionSafetyProfile


class SafetyEngineInput(BaseModel):
    recommendations: list[LLMRecommendation]
    health_profile: dict = Field(default_factory=dict)
    normalized_labs: list[NormalizedLabResult] = Field(default_factory=list)


class MedicationRead(BaseModel):
    name: str
    drug_class: str | None = None
    aliases: list[str] = []


class SafetyConditionRead(BaseModel):
    key: str
    label: str


class SafetyGraphEdgeRead(BaseModel):
    intervention: str
    relationship: SafetyRelationshipType
    target: str
    severity: SafetyRiskLevel
    mechanism: str
    evidence_level: SafetyWarningEvidenceLevel | None = None
    citations: list[str] = []


class InterventionSafetyEvaluateResponse(BaseModel):
    intervention_name: str
    safety_profile: InterventionSafetyProfile