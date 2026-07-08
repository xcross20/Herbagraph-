"""Shared study-quality weighting used by all evidence source integrations."""

from app.models.enums import StudyType

STUDY_TYPE_WEIGHTS: dict[StudyType, float] = {
    StudyType.META_ANALYSIS: 1.00,
    StudyType.SYSTEMATIC_REVIEW: 0.90,
    StudyType.RCT: 0.85,
    StudyType.COHORT: 0.60,
    StudyType.CASE_CONTROL: 0.45,
    StudyType.MECHANISTIC: 0.40,
    StudyType.PRECLINICAL: 0.20,
    StudyType.ANIMAL: 0.25,
    StudyType.IN_VITRO: 0.18,
    StudyType.TRADITIONAL_USE: 0.15,
}


def classify_study_type(title: str, publication_types: list[str] | None = None) -> StudyType:
    """Best-effort classification of a study's type from its title and/or publication type tags."""
    haystack = " ".join([title or "", *(publication_types or [])]).lower()

    if "meta-analysis" in haystack or "meta analysis" in haystack:
        return StudyType.META_ANALYSIS
    if "systematic review" in haystack:
        return StudyType.SYSTEMATIC_REVIEW
    if "randomized" in haystack or "rct" in haystack or "randomised" in haystack:
        return StudyType.RCT
    if "cohort" in haystack:
        return StudyType.COHORT
    if "case-control" in haystack or "case control" in haystack:
        return StudyType.CASE_CONTROL
    if "in vitro" in haystack or "cell culture" in haystack:
        return StudyType.IN_VITRO
    if "animal" in haystack or "mice" in haystack or "rat model" in haystack:
        return StudyType.ANIMAL
    if "mechanistic" in haystack or "mechanism" in haystack:
        return StudyType.MECHANISTIC
    if "traditional" in haystack or "ayurved" in haystack or "ethnobotanical" in haystack:
        return StudyType.TRADITIONAL_USE
    return StudyType.PRECLINICAL


def quality_score_for(study_type: StudyType) -> float:
    return STUDY_TYPE_WEIGHTS[study_type]
