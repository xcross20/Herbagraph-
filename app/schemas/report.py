import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import (
    EvidenceLevel,
    EvidenceTier,
    InterventionCategory,
    LabResultStatus,
    PathwayDirection,
    SafetyRiskLevel,
    StudySource,
    StudyType,
)
from app.schemas.evidence import FoodSourceRead


class PathwayActivationRead(BaseModel):
    pathway_code: str
    pathway_name: str
    activation_score: float
    direction: PathwayDirection
    contributing_biomarkers: list[str] = []


class BiomarkerInterpretation(BaseModel):
    """Plain-language interpretation of a single abnormal biomarker (the "Biomarker
    interpretation" output, distinct from the aggregate BiomarkerSummary counts)."""

    biomarker_name: str
    status: LabResultStatus
    interpretation: str


class RecommendationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rank: int
    intervention_name: str
    category: InterventionCategory
    mechanism: str | None = None
    evidence_level: EvidenceLevel
    evidence_tier: EvidenceTier
    evidence_tier_label: str
    confidence_score: float
    typical_dose: str | None = None
    rationale: str | None = None
    limitations: str | None = None
    safety_risk: SafetyRiskLevel
    safety_notes: list[str] = []
    interactions: list[str] = []
    is_regulated: bool
    cited_study_ids: list[str] = []
    cited_urls: list[str] = []
    food_sources: list[FoodSourceRead] | None = None


class CitationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source: StudySource
    title: str
    year: int | None = None
    study_type: StudyType | None = None
    quality_score: float | None = None


class BiomarkerSummary(BaseModel):
    total_biomarkers: int
    abnormal_count: int
    normal_count: int
    categories_affected: dict[str, int] = {}


class SafetySummary(BaseModel):
    overall_note: str
    requires_clinician_review: bool
    high_risk_interventions: list[str] = []


class RecommendationReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    lab_report_id: uuid.UUID
    overall_confidence: float
    model_version: str
    executive_summary: str
    biomarker_summary: BiomarkerSummary
    biomarker_interpretations: list[BiomarkerInterpretation] = []
    pathway_activations: list[PathwayActivationRead]
    recommendations: list[RecommendationRead]
    citations: list[CitationRead]
    clinician_questions: list[str]
    safety_summary: SafetySummary
    disclaimer: str
    created_at: datetime


class RecommendationReportSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    lab_report_id: uuid.UUID
    overall_confidence: float
    created_at: datetime
