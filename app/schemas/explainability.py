"""Structured explainability payloads — confidence originates here, never from the LLM."""

from __future__ import annotations


from pydantic import BaseModel, Field

from app.models.enums import EvidenceConfidenceLevel, EvidenceQualityGrade, StudyOutcome


class ConfidenceFactor(BaseModel):
    """One transparent factor in the confidence algorithm."""

    factor: str
    weight: float
    raw_score: float = Field(ge=0.0, le=1.0)
    weighted_contribution: float
    explanation: str


class SupportingBiomarker(BaseModel):
    biomarker_name: str
    status: str | None = None
    contribution_strength: float = Field(ge=0.0, le=1.0)
    pathway_codes: list[str] = []


class SupportingPathway(BaseModel):
    pathway_code: str
    pathway_name: str
    activation_score: float = Field(ge=0.0, le=1.0)
    confidence: EvidenceConfidenceLevel
    direction: str | None = None


class MolecularTarget(BaseModel):
    name: str
    compound: str | None = None
    source: str = "knowledge_graph"
    provenance_node: str | None = None


class ExplanationChainLink(BaseModel):
    """Single link in biomarker → pathway → mechanism → intervention → evidence."""

    link_type: str
    label: str
    detail: str | None = None


class SupportingLiteratureEntry(BaseModel):
    """One study — shared by passport counts, supporting literature links, and citations table."""

    study_id: str
    label: str
    title: str
    year: int | None = None
    study_type: str | None = None
    url: str | None = None


class EvidenceTimelineEntry(BaseModel):
    year: int
    label: str
    study_id: str | None = None
    study_type: str | None = None


class StudyOutcomeSummary(BaseModel):
    study_id: str
    title: str
    outcome: StudyOutcome
    year: int | None = None
    study_type: str | None = None


class ContradictoryEvidence(BaseModel):
    positive_count: int = 0
    neutral_count: int = 0
    negative_count: int = 0
    positive_percent: float = Field(ge=0.0, le=100.0)
    neutral_percent: float = Field(ge=0.0, le=100.0)
    negative_percent: float = Field(ge=0.0, le=100.0)
    disagreement_summary: str = ""
    studies: list[StudyOutcomeSummary] = []


class PopulationApplicability(BaseModel):
    """Best-effort population context from retrieved studies and patient profile."""

    age_range: str | None = None
    sex: str | None = None
    disease_states: list[str] = []
    bmi_notes: list[str] = []
    sample_sizes: list[int] = []
    countries: list[str] = []
    treatment_durations: list[str] = []
    doses: list[str] = []
    extraction_notes: list[str] = []


class ResearchGap(BaseModel):
    gap: str
    severity: str = "moderate"


class EvidencePassport(BaseModel):
    """Clinician-facing evidence card — the HerbaGraph signature per intervention."""

    quality_stars: int = Field(ge=1, le=5)
    quality_label: str
    confidence_level: EvidenceConfidenceLevel
    confidence_label: str
    meta_analyses: int = 0
    systematic_reviews: int = 0
    rcts: int = 0
    human_studies: int = 0
    conflicting_evidence: bool = False
    population_summary: str = ""
    applicable_to: list[str] = []
    last_updated_year: int | None = None
    research_gaps: list[str] = []
    confidence_why: list[str] = []
    evidence_display_label: str = ""
    why_surfaced: list[str] = []
    primary_pathway: str | None = None
    safety_label: str = "low"
    last_updated_display: str | None = None
    evidence_synthesis_statement: str = ""
    intervention_classes: list[str] = []
    supporting_literature: list[SupportingLiteratureEntry] = []


class GraphProvenance(BaseModel):
    source: str
    external_id: str | None = None
    knowledge_graph_node: str | None = None
    url: str | None = None
    extraction_date: str | None = None
    review_status: str = "auto_retrieved"
    evidence_version: str


class ReportVersioning(BaseModel):
    knowledge_graph_version: str
    evidence_version: str
    reasoning_engine_version: str
    explainability_engine_version: str
    report_generation_version: str
    date_generated: str


class ScoreDimension(BaseModel):
    """One independent confidence axis (0–1). Never copy another axis's value."""

    key: str
    label: str
    score: float = Field(ge=0.0, le=1.0)
    percent: int = Field(ge=0, le=100)
    limiting_factors: list[str] = []


class ConfidenceGapItem(BaseModel):
    """Named information that could change the decision — not a 90% hunt."""

    action: str
    dimension: str
    expected_gain: float = Field(ge=0.0, le=1.0)
    expected_gain_percent: int = Field(ge=0, le=100)
    already_present: bool = False


class ConfidenceDecomposition(BaseModel):
    """Four first-class scores. Decision confidence is not data sufficiency."""

    evidence_confidence: ScoreDimension
    patient_match: ScoreDimension
    data_sufficiency: ScoreDimension
    decision_confidence: ScoreDimension
    contradiction_penalty: float = 0.0
    primary_bottleneck: str
    decision_band: str
    decision_band_explanation: str = ""
    missing_biomarkers: list[str] = []
    missing_context: list[str] = []
    gap_analysis: list[ConfidenceGapItem] = []
    formula_version: str = "decomposition_v1"


class RecommendationExplainability(BaseModel):
    """Full explainability bundle for one recommendation."""

    intervention_name: str
    evidence_confidence_level: EvidenceConfidenceLevel
    evidence_confidence_numeric: float = Field(ge=0.0, le=1.0)
    evidence_quality_grade: EvidenceQualityGrade
    confidence_decomposition: ConfidenceDecomposition | None = None
    confidence_factors: list[ConfidenceFactor] = []
    biological_rationale: str
    explanation_chain: list[ExplanationChainLink] = []
    why_recommended: list[str] = []
    why_not_higher: list[str] = []
    confidence_explanation: str
    supporting_biomarkers: list[SupportingBiomarker] = []
    supporting_pathways: list[SupportingPathway] = []
    molecular_targets: list[MolecularTarget] = []
    supporting_study_ids: list[str] = []
    supporting_literature: list[SupportingLiteratureEntry] = []
    evidence_timeline: list[EvidenceTimelineEntry] = []
    contradictory_evidence: ContradictoryEvidence
    population_applicability: PopulationApplicability
    research_gaps: list[ResearchGap] = []
    provenance: list[GraphProvenance] = []
    evidence_passport: EvidencePassport | None = None
    versioning: ReportVersioning


class ExplainabilityEvaluateInput(BaseModel):
    recommendations: list[dict]
    evidence_snippets: list[dict] = []
    pathway_activations: list[dict] = []
    intervention_pathways: dict[str, list[str]] = {}
    normalized_labs: list[dict] = []
    health_profile: dict = {}


class ExplainabilityEvaluateResponse(BaseModel):
    explainability: list[RecommendationExplainability]
    versioning: ReportVersioning