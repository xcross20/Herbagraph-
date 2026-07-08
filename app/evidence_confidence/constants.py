"""Transparent version strings and scoring weights for the Evidence Confidence Engine."""

from datetime import UTC, datetime

# Engine versions — bump when algorithm or graph semantics change.
KNOWLEDGE_GRAPH_VERSION = "1.2.0"
EVIDENCE_VERSION = "1.0.0"
REASONING_ENGINE_VERSION = "0.1.0"
EXPLAINABILITY_ENGINE_VERSION = "1.0.0"
REPORT_GENERATION_VERSION = "1.0.0"


def current_generation_timestamp() -> str:
    return datetime.now(UTC).isoformat()


# Study-type hierarchy weights for evidence quality grading (higher = stronger).
STUDY_TYPE_HIERARCHY_WEIGHT: dict[str, float] = {
    "meta_analysis": 1.00,
    "systematic_review": 0.95,
    "rct": 0.85,
    "cohort": 0.65,
    "case_control": 0.55,
    "mechanistic": 0.40,
    "preclinical": 0.30,
    "animal": 0.25,
    "in_vitro": 0.20,
    "traditional_use": 0.15,
}

# Per-study-type contribution caps used in the confidence numeric score (transparent factors).
STUDY_TYPE_CONFIDENCE_CAP: dict[str, float] = {
    "meta_analysis": 0.12,
    "systematic_review": 0.10,
    "rct": 0.15,
    "cohort": 0.06,
    "case_control": 0.05,
    "mechanistic": 0.04,
    "preclinical": 0.03,
    "animal": 0.02,
    "in_vitro": 0.01,
}

# Confidence level thresholds (numeric 0–1, before safety adjustment).
CONFIDENCE_HIGH_THRESHOLD = 0.70
CONFIDENCE_MODERATE_THRESHOLD = 0.45

# Evidence quality grade thresholds (weighted hierarchy score 0–1).
QUALITY_VERY_HIGH_THRESHOLD = 0.85
QUALITY_HIGH_THRESHOLD = 0.70
QUALITY_MODERATE_THRESHOLD = 0.50
QUALITY_LOW_THRESHOLD = 0.30

# Recency: full credit for studies within this many years.
RECENCY_FULL_YEARS = 5
RECENCY_DECAY_YEARS = 15

# Graph connectivity: minimum links for full plausibility credit.
GRAPH_LINK_FULL_COUNT = 4