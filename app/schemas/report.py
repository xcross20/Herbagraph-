import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import (
    EvidenceLevel,
    EvidenceTier,
    InterventionCategory,
    LabResultStatus,
    PathwayDirection,
    ReportGenerationStage,
    SafetyRiskLevel,
    StudySource,
    StudyType,
)
from app.schemas.evidence import FoodSourceRead
from app.schemas.explainability import RecommendationExplainability, ReportVersioning, SupportingLiteratureEntry
from app.schemas.safety_profile import InterventionSafetyProfile


class PathwayActivationRead(BaseModel):
    """Detailed/internal 16-pathway breakdown. `activation_score` is an evidence-weighted
    signal strength (0-1) derived from lab values and pathway-mapping rules, NOT a direct
    biological measurement. Most consumers should prefer `biological_systems` below, which
    rolls this up into 7 systems with a simpler 0-3 signal scale."""

    pathway_code: str
    pathway_name: str
    activation_score: float
    direction: PathwayDirection
    contributing_biomarkers: list[str] = []


class BiologicalSystemPathwayRef(BaseModel):
    pathway_code: str
    pathway_name: str


class BiologicalSystemRead(BaseModel):
    """The recommended user-facing view: 7 biological systems with a simple 0-3 signal
    score, in place of the 16 internal pathways. See app/pipeline/biological_systems.py."""

    system_code: str
    system_name: str
    signal_level: int
    signal_label: str
    direction: str
    confidence: str
    drivers: list[str] = []
    pathways: list[BiologicalSystemPathwayRef] = []


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
    intervention_narrative: str | None = None
    safety_profile: InterventionSafetyProfile | None = None
    explainability: RecommendationExplainability | None = None
    supporting_literature: list[SupportingLiteratureEntry] = []


class CitationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source: StudySource
    title: str
    year: int | None = None
    study_type: StudyType | None = None
    quality_score: float | None = None
    url: str | None = None


class MeasuredBiomarkerRead(BaseModel):
    biomarker_name: str
    value: float
    unit: str | None = None
    status: LabResultStatus
    category: str | None = None
    qualitative_label: str | None = None
    expected_label: str | None = None
    reference_range_low: float | None = None
    reference_range_high: float | None = None
    in_catalog: bool = True
    in_profile: bool = False


class BiomarkerSummary(BaseModel):
    total_biomarkers: int
    abnormal_count: int
    normal_count: int
    categories_affected: dict[str, int] = {}
    measured_biomarkers: list[MeasuredBiomarkerRead] = []


class SafetySummary(BaseModel):
    overall_note: str
    requires_clinician_review: bool
    high_risk_interventions: list[str] = []


class MedicationContextRead(BaseModel):
    has_medications: bool = False
    medications: list[str] = []
    supplements: list[str] = []
    notes: list[str] = []
    biomarker_specific_notes: list[dict] = []


class LabTrendEntry(BaseModel):
    biomarker_name: str
    prior_value: float
    current_value: float
    unit: str | None = None
    delta: float
    direction: str
    prior_status: str
    current_status: str


class LabTrendsRead(BaseModel):
    has_prior_labs: bool = False
    prior_report_date: str | None = None
    compared_biomarkers: int = 0
    improved_count: int = 0
    worsened_count: int = 0
    unchanged_count: int = 0
    trends: list[LabTrendEntry] = []
    summary: str = ""


class ClinicalSummaryHeroRead(BaseModel):
    """Page-1 stitched clinical summary."""

    model: str = "clinical_summary_hero_v1"
    positioning: str = "AI Clinical Reasoning for Precision Nutrition"
    title: str = "HerbaGraph Clinical Summary"
    overall_confidence_label: str = ""
    overall_confidence_percent: int | None = None
    primary_finding: dict = {}
    likely_explanation: str = ""
    alternative_explanations: list[str] = []
    diagnostic_note: str | None = None
    most_important_next_tests: list[dict] = []
    highest_leverage_interventions: list[dict] = []
    confidence_if_added: list[dict] = []
    secondary_priorities: list[dict] = []


class DualClinicalRankingsRead(BaseModel):
    """Separate clinical-priority and network-leverage rankings."""

    model: str = "dual_ranking_v1"
    clinical_priorities: list[dict] = []
    network_leverage_groups: list[dict] = []
    clinical_priority_table: list[dict] = []
    ranking_questions: dict = {}


class BiologicalHierarchyRead(BaseModel):
    """Biology-first cascade: biomarkers → systems → pathways → interventions."""

    model: str = "biology_hierarchy_v1"
    cascade: dict = {}
    abnormal_biomarker_details: list[dict] = []
    dominant_biology: dict | None = None
    systems_tree: list[dict] = []
    network_influence_table: list[dict] = []
    ranking_priorities: list[str] = []


class RecommendationTiersRead(BaseModel):
    """Clinician-focused tiered presentation of evidence-graded considerations."""

    model: str = "tiered_v1"
    caps: dict = {}
    top_biological_problems: list[dict] = []
    top_considerations: list[dict] = []
    additional_by_category: dict = {}
    regulated_context: dict = {}
    mechanistic_appendix: dict = {}
    full_appendix_available: bool = False
    total_considerations: int = 0
    displayed_by_default: int = 0
    clinical_executive_summary: str = ""


class RecommendationReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    lab_report_id: uuid.UUID
    overall_confidence: float
    model_version: str
    executive_summary: str
    biomarker_summary: BiomarkerSummary
    biomarker_interpretations: list[BiomarkerInterpretation] = []
    biological_systems: list[BiologicalSystemRead] = []
    pathway_activations: list[PathwayActivationRead]
    recommendations: list[RecommendationRead]
    citations: list[CitationRead]
    clinician_questions: list[str]
    safety_summary: SafetySummary
    medication_context: MedicationContextRead = MedicationContextRead()
    lab_trends: LabTrendsRead = LabTrendsRead()
    disclaimer: str
    report_versioning: ReportVersioning | None = None
    evidence_summary: dict | None = None
    missing_information: dict | None = None
    overall_confidence_assessment: dict | None = None
    biological_reasoning_summary: dict | None = None
    differential_explanations: dict | None = None
    patient_evidence_gaps: dict | None = None
    report_methodology: dict | None = None
    report_insights: dict | None = None
    recommendation_tiers: RecommendationTiersRead | None = None
    biological_hierarchy: BiologicalHierarchyRead | None = None
    dual_clinical_rankings: DualClinicalRankingsRead | None = None
    clinical_summary_hero: ClinicalSummaryHeroRead | None = None
    created_at: datetime


class RecommendationReportSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    lab_report_id: uuid.UUID
    overall_confidence: float
    created_at: datetime


class ReportGenerationResponse(BaseModel):
    lab_report_id: uuid.UUID
    task_id: str
    report_stage: ReportGenerationStage
    message: str
