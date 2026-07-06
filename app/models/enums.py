import enum


class UserRole(str, enum.Enum):
    """Distinguishes a self-service individual account from a clinic account that
    manages multiple Patients (Phase 4 infrastructure -- see app/models/patient.py)."""

    INDIVIDUAL = "individual"
    CLINICIAN = "clinician"


class LabReportStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETE = "complete"
    FAILED = "failed"


class LabProcessingStage(str, enum.Enum):
    """Granular progress for Stage 1–2 (lab parse + biomarker normalization)."""

    QUEUED = "queued"
    PARSING = "parsing"
    NORMALIZING = "normalizing"
    COMPLETE = "complete"
    FAILED = "failed"


class ReportGenerationStage(str, enum.Enum):
    """Granular progress for Stage 3–7 (pathways through final report)."""

    QUEUED = "queued"
    PATHWAY_MAPPING = "pathway_mapping"
    EVIDENCE_RETRIEVAL = "evidence_retrieval"
    LLM_REASONING = "llm_reasoning"
    SAFETY_CHECK = "safety_check"
    REPORT_ASSEMBLY = "report_assembly"
    COMPLETE = "complete"
    FAILED = "failed"


class LabResultStatus(str, enum.Enum):
    CRITICAL_LOW = "critical_low"
    LOW = "low"
    OPTIMAL = "optimal"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL_HIGH = "critical_high"


class InterventionCategory(str, enum.Enum):
    """The intervention ontology. Everything the graph reasons about -- a food, an isolated
    phytochemical, a supplement, a workout, a medication -- is one of these. None is treated
    as inherently more "medical" than another; they differ only in evidence and safety profile."""

    FOOD = "food"
    HERB = "herb"
    PHYTOCHEMICAL = "phytochemical"
    SUPPLEMENT = "supplement"
    EXERCISE = "exercise"
    SLEEP = "sleep"
    STRESS_REDUCTION = "stress_reduction"
    MEDICATION = "medication"
    PEPTIDE = "peptide"
    HORMONE = "hormone"
    ENVIRONMENTAL = "environmental"
    BEHAVIOR = "behavior"


class EvidenceLevel(str, enum.Enum):
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    PRECLINICAL = "preclinical"


class EvidenceTier(str, enum.Enum):
    """Where a recommendation's cited evidence sits in the evidence hierarchy. Distinct from
    EvidenceLevel: EvidenceLevel is a per-claim strength rating used in confidence scoring;
    EvidenceTier is the user-facing label answering "how much should I trust this, and why."
    Established/Emerging/Preclinical/Research Hypothesis are derived automatically from the
    actual cited studies (see report_generator.determine_evidence_tier); Traditional Use and
    Historical/Ethnobotanical are reserved for a future traditional-medicine evidence source --
    HerbaGraph does not currently retrieve or label anything as traditional-medicine evidence,
    so those two tiers are never assigned automatically today."""

    ESTABLISHED = "established"
    EMERGING = "emerging"
    PRECLINICAL = "preclinical"
    RESEARCH_HYPOTHESIS = "research_hypothesis"
    TRADITIONAL_USE = "traditional_use"
    HISTORICAL_ETHNOBOTANICAL = "historical_ethnobotanical"


EVIDENCE_TIER_LABELS: dict["EvidenceTier", str] = {
    EvidenceTier.ESTABLISHED: "Established Evidence",
    EvidenceTier.EMERGING: "Emerging Evidence",
    EvidenceTier.PRECLINICAL: "Preclinical Evidence",
    EvidenceTier.RESEARCH_HYPOTHESIS: "Research Hypothesis",
    EvidenceTier.TRADITIONAL_USE: "Traditional Use (Ayurveda/TCM)",
    EvidenceTier.HISTORICAL_ETHNOBOTANICAL: "Historical/Ethnobotanical Use",
}


class SafetyRiskLevel(str, enum.Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CONTRAINDICATED = "contraindicated"


class StudySource(str, enum.Enum):
    PUBMED = "pubmed"
    CLINICALTRIALS = "clinicaltrials"
    EUROPEPMC = "europepmc"


class StudyType(str, enum.Enum):
    META_ANALYSIS = "meta_analysis"
    SYSTEMATIC_REVIEW = "systematic_review"
    RCT = "rct"
    COHORT = "cohort"
    CASE_CONTROL = "case_control"
    PRECLINICAL = "preclinical"


class Richness(str, enum.Enum):
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"


class PathwayDirection(str, enum.Enum):
    ACTIVATED = "activated"
    SUPPRESSED = "suppressed"


class FlagSeverity(str, enum.Enum):
    CAUTION = "caution"
    CONTRAINDICATION = "contraindication"
