"""Evidence quality grading — accepted hierarchy, no LLM involvement."""

from __future__ import annotations

from app.evidence_confidence.constants import (
    QUALITY_HIGH_THRESHOLD,
    QUALITY_LOW_THRESHOLD,
    QUALITY_MODERATE_THRESHOLD,
    QUALITY_VERY_HIGH_THRESHOLD,
    STUDY_TYPE_HIERARCHY_WEIGHT,
)
from app.models.enums import EvidenceQualityGrade, StudyType
from app.schemas.pipeline import EvidenceSnippet


def _study_type_key(study_type: StudyType | None) -> str:
    if study_type is None:
        return "preclinical"
    return study_type.value


def grade_evidence_quality(cited: list[EvidenceSnippet]) -> tuple[EvidenceQualityGrade, float, str]:
    """Return (grade, numeric_score, explanation) from cited studies only."""
    if not cited:
        return (
            EvidenceQualityGrade.VERY_LOW,
            0.0,
            "No retrieved studies were cited for this recommendation.",
        )

    weights = [STUDY_TYPE_HIERARCHY_WEIGHT.get(_study_type_key(e.study_type), 0.20) for e in cited]
    quality_scores = [e.quality_score for e in cited]
    # Blend hierarchy peak with mean quality — transparent, not hidden.
    peak = max(weights)
    mean_quality = sum(quality_scores) / len(quality_scores)
    numeric = round(0.65 * peak + 0.35 * mean_quality, 4)

    if numeric >= QUALITY_VERY_HIGH_THRESHOLD:
        grade = EvidenceQualityGrade.VERY_HIGH
    elif numeric >= QUALITY_HIGH_THRESHOLD:
        grade = EvidenceQualityGrade.HIGH
    elif numeric >= QUALITY_MODERATE_THRESHOLD:
        grade = EvidenceQualityGrade.MODERATE
    elif numeric >= QUALITY_LOW_THRESHOLD:
        grade = EvidenceQualityGrade.LOW
    else:
        grade = EvidenceQualityGrade.VERY_LOW

    best_type = max(cited, key=lambda e: STUDY_TYPE_HIERARCHY_WEIGHT.get(_study_type_key(e.study_type), 0))
    best_label = _study_type_key(best_type.study_type).replace("_", " ")
    explanation = (
        f"Quality grade derived from {len(cited)} cited study/studies; "
        f"strongest design: {best_label} (hierarchy weight "
        f"{STUDY_TYPE_HIERARCHY_WEIGHT.get(_study_type_key(best_type.study_type), 0.2):.2f})."
    )
    return grade, numeric, explanation