import enum


class UserRole(str, enum.Enum):
    """Account role for workspace permissions."""

    INDIVIDUAL = "individual"
    CLINICIAN = "clinician"
    ADMIN = "admin"
    ORGANIZATION_ADMIN = "organization_admin"


class AnalysisType(str, enum.Enum):
    SINGLE_REPORT = "single_report"
    MULTI_REPORT_SNAPSHOT = "multi_report_snapshot"
    LONGITUDINAL_COMPARISON = "longitudinal_comparison"


class PatientContextType(str, enum.Enum):
    MEDICATION = "medication"
    SUPPLEMENT = "supplement"
    CONDITION = "condition"
    ALLERGY = "allergy"
    DIET_PATTERN = "diet_pattern"
    SYMPTOM = "symptom"
    GOAL = "goal"
    NOTE = "note"


class AuditAction(str, enum.Enum):
    USER_REGISTERED = "user_registered"
    USER_LOGIN = "user_login"
    USER_SYNC = "user_sync"
    USER_UPDATED = "user_updated"
    USER_DELETED = "user_deleted"
    PATIENT_CREATED = "patient_created"
    PATIENT_UPDATED = "patient_updated"
    LAB_UPLOADED = "lab_uploaded"
    LAB_PARSED = "lab_parsed"
    LAB_PARSE_FAILED = "lab_parse_failed"
    LAB_FILE_DOWNLOADED = "lab_file_downloaded"
    BIOMARKER_CORRECTED = "biomarker_corrected"
    ANALYSIS_STARTED = "analysis_started"
    ANALYSIS_COMPLETED = "analysis_completed"
    ANALYSIS_FAILED = "analysis_failed"
    REPORT_GENERATED = "report_generated"
    REPORT_VIEWED = "report_viewed"
    REPORT_DOWNLOADED = "report_downloaded"
    CONTEXT_ADDED = "context_added"


class DiscoveryCaseStatus(str, enum.Enum):
    OPEN = "open"
    PAUSED = "paused"
    CLOSED = "closed"


class DiscoveryFindingKind(str, enum.Enum):
    CONCERN = "concern"
    LAB = "lab"
    CONTEXT = "context"
    ASSESSMENT = "assessment"
    SYMPTOM = "symptom"


class DiscoveryOutcomeStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    NOT_DONE = "not_done"
    DEFERRED = "deferred"


class DiscoveryTurnRole(str, enum.Enum):
    USER = "user"
    SYSTEM = "system"


class DiscoveryHypothesisStatus(str, enum.Enum):
    """Hypotheses stay open until a clinician marks them. The engine never auto-diagnoses."""

    OPEN = "open"
    WATCH = "watch"
    DEFERRED = "deferred"


class PatientContextSource(str, enum.Enum):
    USER = "user"
    IMPORT = "import"
    SYSTEM = "system"


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


class AnalysisSessionStatus(str, enum.Enum):
    PENDING = "pending"
    PARSING = "parsing"
    MERGING = "merging"
    ANALYZING = "analyzing"
    COMPLETE = "complete"
    FAILED = "failed"


class ReportGenerationStage(str, enum.Enum):
    """Granular progress for Stage 3–8 (pathways through final report)."""

    QUEUED = "queued"
    PATHWAY_MAPPING = "pathway_mapping"
    EVIDENCE_RETRIEVAL = "evidence_retrieval"
    LLM_REASONING = "llm_reasoning"
    EVIDENCE_CONFIDENCE = "evidence_confidence"
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


class PathwayType(str, enum.Enum):
    """Distinguishes host signaling pathways from etiological (root-cause) pathways."""

    SIGNALING = "signaling"
    ETIOLOGICAL = "etiological"


class RecommendationTree(str, enum.Enum):
    """Which reasoning tree applies for a given abnormal lab result."""

    SIGNALING = "signaling"
    ETIOLOGICAL = "etiological"
    EXPOSURE = "exposure"
    CULTURE = "culture"
    CELIAC = "celiac"
    ALLERGY = "allergy"
    PGX_CONTEXT = "pgx_context"
    NUTRITIONAL_REPLETION = "nutritional_repletion"
    AUTOIMMUNE = "autoimmune"


class RecommendationIntent(str, enum.Enum):
    """Why an intervention is surfaced relative to the active recommendation tree."""

    PRIMARY = "primary"
    COLLATERAL = "collateral"
    CONTEXT_ONLY = "context_only"
    NUTRITIONAL_REPLETION = "nutritional_repletion"


class DisplayIntent(str, enum.Enum):
    """User-facing report tier label — controls default visibility and section placement."""

    PRIMARY = "primary"
    SUPPORTIVE = "supportive"
    CONTEXT_ONLY = "context_only"
    REGULATED = "regulated"
    MECHANISTIC = "mechanistic"


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
    MECHANISTIC = "mechanistic"
    PRECLINICAL = "preclinical"
    ANIMAL = "animal"
    IN_VITRO = "in_vitro"
    TRADITIONAL_USE = "traditional_use"


class EvidenceConfidenceLevel(str, enum.Enum):
    """User-facing confidence band — always computed from structured evidence, never LLM."""

    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"


class EvidenceQualityGrade(str, enum.Enum):
    """Evidence hierarchy grade per recommendation."""

    VERY_HIGH = "very_high"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    VERY_LOW = "very_low"


EVIDENCE_QUALITY_LABELS: dict["EvidenceQualityGrade", str] = {
    EvidenceQualityGrade.VERY_HIGH: "Very High",
    EvidenceQualityGrade.HIGH: "High",
    EvidenceQualityGrade.MODERATE: "Moderate",
    EvidenceQualityGrade.LOW: "Low",
    EvidenceQualityGrade.VERY_LOW: "Very Low",
}


EVIDENCE_CONFIDENCE_LABELS: dict["EvidenceConfidenceLevel", str] = {
    EvidenceConfidenceLevel.HIGH: "High",
    EvidenceConfidenceLevel.MODERATE: "Moderate",
    EvidenceConfidenceLevel.LOW: "Low",
}


class StudyOutcome(str, enum.Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


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


class SafetyNodeType(str, enum.Enum):
    """Safety graph entity types — extensible without schema changes."""

    MEDICATION = "medication"
    SUPPLEMENT = "supplement"
    BOTANICAL = "botanical"
    FOOD_COMPOUND = "food_compound"
    PEPTIDE = "peptide"
    LIFESTYLE = "lifestyle"
    CONDITION = "condition"
    ORGAN_SYSTEM = "organ_system"
    INTERVENTION = "intervention"


class SafetyRelationshipType(str, enum.Enum):
    INTERACTS_WITH = "interacts_with"
    CONTRAINDICATED_IN = "contraindicated_in"
    USE_WITH_CAUTION = "use_with_caution"
    CAUTION_IN = "caution_in"
    AFFECTS_PATHWAY = "affects_pathway"


class CanonicalEntityType(str, enum.Enum):
    """Level 1 intervention universe taxonomy."""

    FOOD = "food"
    BOTANICAL = "botanical"
    NUTRIENT = "nutrient"
    SUPPLEMENT = "supplement"
    COMPOUND = "compound"
    LIFESTYLE = "lifestyle"
    MEDICATION = "medication"
    PEPTIDE = "peptide"
    PROCEDURE = "procedure"
    DEVICE = "device"
    PATHWAY = "pathway"
    BIOMARKER = "biomarker"


class CanonicalEntitySubtype(str, enum.Enum):
    """Finer classification within entity_type (foods, botanicals, nutrients, supplements)."""

    # Foods
    FRUIT = "fruit"
    VEGETABLE = "vegetable"
    LEGUME = "legume"
    WHOLE_GRAIN = "whole_grain"
    NUT = "nut"
    SEED = "seed"
    MUSHROOM = "mushroom"
    SEA_VEGETABLE = "sea_vegetable"
    SPICE = "spice"
    BEVERAGE = "beverage"
    FERMENTED_FOOD = "fermented_food"
    # Botanicals
    HERB = "herb"
    ROOT = "root"
    BARK = "bark"
    RHIZOME = "rhizome"
    FLOWER = "flower"
    BOTANICAL_SEED = "botanical_seed"
    BOTANICAL_FRUIT = "botanical_fruit"
    LEAF = "leaf"
    RESIN = "resin"
    EXTRACT = "extract"
    # Nutrients
    VITAMIN = "vitamin"
    MINERAL = "mineral"
    AMINO_ACID = "amino_acid"
    FATTY_ACID = "fatty_acid"
    FIBER = "fiber"
    OTHER_NUTRIENT = "other_nutrient"
    # Supplements
    ISOLATED_COMPOUND = "isolated_compound"
    STANDARDIZED_EXTRACT = "standardized_extract"
    METABOLITE = "metabolite"
    PROBIOTIC = "probiotic"
    ENZYME = "enzyme"
    MULTI_INGREDIENT = "multi_ingredient"
    OTHER = "other"


class EntityReviewStatus(str, enum.Enum):
    """Graph publication lifecycle — nodes and edges."""

    MACHINE_GENERATED = "machine_generated"
    MACHINE_VERIFIED = "machine_verified"
    HUMAN_REVIEWED = "human_reviewed"
    PRODUCTION_APPROVED = "production_approved"
    DEPRECATED = "deprecated"


class CoverageTier(str, enum.Enum):
    """Entity maturity tier for recommendation surfacing."""

    TIER_A = "tier_a"
    TIER_B = "tier_b"
    TIER_C = "tier_c"


class GraphRelationshipType(str, enum.Enum):
    """Biological/compositional edge types."""

    CONTAINS = "contains"
    INCLUDES = "includes"
    MODULATES = "modulates"
    INFLUENCES = "influences"
    TARGETS = "targets"
    ACTIVATES = "activates"
    INHIBITS = "inhibits"


class GraphEvidenceType(str, enum.Enum):
    """Evidence strength for graph edges (Level 4)."""

    PREDICTED = "predicted"
    MECHANISTIC = "mechanistic"
    ANIMAL = "animal"
    OBSERVATIONAL_HUMAN = "observational_human"
    CLINICAL_HUMAN = "clinical_human"
    META_ANALYTIC = "meta_analytic"


class ExternalIdSource(str, enum.Enum):
    PUBCHEM = "pubchem"
    CHEBI = "chebi"
    USDA_FDC = "usda_fdc"
    NCBI_TAXON = "ncbi_taxon"
    INTERVENTION = "intervention"
    COMPOUND = "compound"


class EnrichmentQueueStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"


class KnowledgePath(str, enum.Enum):
    """Which knowledge substrate drives intervention selection during report analysis.

    LEGACY — curated intervention catalogs + tier_a evidence claims (production default).
    CANONICAL — canonical_entities registry + composition graph, filtered to registry nodes.
    """

    LEGACY = "legacy"
    CANONICAL = "canonical"


class SafetyWarningEvidenceLevel(str, enum.Enum):
    """Evidence strength supporting a safety warning (distinct from intervention evidence)."""

    META_ANALYSIS = "meta_analysis"
    RCT = "rct"
    OBSERVATIONAL = "observational"
    MECHANISTIC = "mechanistic"
    ANIMAL = "animal"
    TRADITIONAL = "traditional"
