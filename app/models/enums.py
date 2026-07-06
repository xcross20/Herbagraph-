import enum


class LabReportStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
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
    HERB = "herb"
    NUTRACEUTICAL = "nutraceutical"
    LIFESTYLE = "lifestyle"
    PEPTIDE = "peptide"
    NAD_PRECURSOR = "nad_precursor"
    FOOD = "food"
    PHYTOCHEMICAL = "phytochemical"
    MEDICATION = "medication"
    HORMONE = "hormone"
    ENVIRONMENTAL = "environmental"
    BEHAVIOR = "behavior"


class EvidenceLevel(str, enum.Enum):
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    PRECLINICAL = "preclinical"


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
