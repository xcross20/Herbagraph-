"""Pydantic models passed between the 7 pipeline stages (see app/pipeline/orchestrator.py)."""

from pydantic import BaseModel, Field

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


class ParsedLabResult(BaseModel):
    """Output of Stage 1 (lab_parser): a single row extracted from a raw lab report."""

    raw_test_name: str
    value: float
    unit: str | None = None
    reference_range_low: float | None = None
    reference_range_high: float | None = None
    raw_line: str | None = None


class NormalizedLabResult(BaseModel):
    """Output of Stage 2 (biomarker_normalizer)."""

    biomarker_name: str
    raw_test_name: str
    value: float
    unit: str | None = None
    reference_range_low: float | None = None
    reference_range_high: float | None = None
    status: LabResultStatus
    category: str | None = None


class PathwayActivation(BaseModel):
    """Output of Stage 3 (pathway_mapper)."""

    pathway_code: str
    pathway_name: str
    activation_score: float = Field(ge=0.0, le=1.0)
    direction: PathwayDirection
    contributing_biomarkers: list[str] = []


class EvidenceSnippet(BaseModel):
    """Output of Stage 4 (evidence_retriever): one retrieved study/trial relevant to an intervention."""

    source: StudySource
    external_id: str
    title: str
    year: int | None = None
    study_type: StudyType | None = None
    quality_score: float = Field(ge=0.0, le=1.0)
    url: str | None = None
    abstract_snippet: str | None = None
    intervention_name: str


class LLMRecommendation(BaseModel):
    """A single recommendation as returned by Stage 5 (llm_reasoner), pre-safety-check.

    `rationale` answers "why was this surfaced" and `limitations` answers "what this
    evidence does NOT show" -- both are required so every recommendation "shows its work"
    rather than presenting as a black-box verdict.
    """

    intervention_name: str
    category: InterventionCategory
    mechanism: str
    evidence_level: EvidenceLevel
    typical_dose: str | None = None
    cited_study_ids: list[str] = []
    rationale: str | None = None
    limitations: str | None = None


class LLMReasoningOutput(BaseModel):
    """Full structured output of Stage 5 (llm_reasoner)."""

    biomarker_pattern_analysis: str
    pathway_summaries: list[str] = []
    recommendations: list[LLMRecommendation] = []
    clinician_questions: list[str] = []


class ScoredRecommendation(LLMRecommendation):
    """A recommendation after Stage 6 (safety_layer) and Stage 7 (report_generator) scoring.

    `evidence_tier`/`evidence_tier_label` are computed deterministically from the actual
    cited studies (see report_generator.determine_evidence_tier) rather than asserted by the
    LLM, so the tier a user sees can't drift from what's really been retrieved.
    """

    safety_risk: SafetyRiskLevel = SafetyRiskLevel.LOW
    safety_notes: list[str] = []
    interactions: list[str] = []
    is_regulated: bool = False
    cited_urls: list[str] = []
    confidence_score: float | None = None
    food_sources: list[FoodSourceRead] | None = None
    evidence_tier: EvidenceTier = EvidenceTier.RESEARCH_HYPOTHESIS
    evidence_tier_label: str = "Research Hypothesis"


class SafetyReport(BaseModel):
    """Output of Stage 6 (safety_layer)."""

    approved_recommendations: list[ScoredRecommendation] = []
    excluded_recommendations: list[ScoredRecommendation] = []
    requires_clinician_review: bool = False
    overall_note: str = "No major drug-herb interactions detected."
