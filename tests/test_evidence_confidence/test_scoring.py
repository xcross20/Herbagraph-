"""Unit tests for Evidence Confidence scoring and quality algorithms."""

import pytest

from app.evidence_confidence.quality import grade_evidence_quality
from app.evidence_confidence.scoring import classify_study_outcome, compute_confidence_score
from app.models.enums import EvidenceConfidenceLevel, EvidenceQualityGrade, StudySource, StudyType
from app.schemas.pipeline import EvidenceSnippet

pytestmark = pytest.mark.unit


def _snippet(
    external_id: str,
    study_type: StudyType,
    quality_score: float,
    year: int = 2022,
    abstract: str | None = None,
) -> EvidenceSnippet:
    return EvidenceSnippet(
        source=StudySource.PUBMED,
        external_id=external_id,
        title=f"Study {external_id}",
        year=year,
        study_type=study_type,
        quality_score=quality_score,
        intervention_name="Curcumin",
        abstract_snippet=abstract,
    )


def test_grade_very_high_from_meta_analysis():
    cited = [_snippet("pm1", StudyType.META_ANALYSIS, 0.9, 2024)]
    grade, numeric, explanation = grade_evidence_quality(cited)
    assert grade == EvidenceQualityGrade.VERY_HIGH
    assert numeric >= 0.85
    assert "meta analysis" in explanation.lower()


def test_grade_very_low_without_citations():
    grade, numeric, _ = grade_evidence_quality([])
    assert grade == EvidenceQualityGrade.VERY_LOW
    assert numeric == 0.0


def test_confidence_high_with_multiple_rcts():
    cited = [
        _snippet("r1", StudyType.RCT, 0.8, 2023),
        _snippet("r2", StudyType.RCT, 0.75, 2024),
        _snippet("sr1", StudyType.SYSTEMATIC_REVIEW, 0.85, 2025),
    ]
    numeric, level, factors, _ = compute_confidence_score(
        cited,
        pathway_count=2,
        biomarker_count=2,
        has_mechanism=True,
        target_count=1,
        safety_data_available=True,
        current_year=2026,
    )
    assert level in (EvidenceConfidenceLevel.HIGH, EvidenceConfidenceLevel.MODERATE)
    assert numeric > 0.4
    factor_names = {f.factor for f in factors}
    assert "publication_recency" in factor_names
    assert "consistency_across_studies" in factor_names


def test_confidence_low_without_evidence():
    numeric, level, _, _ = compute_confidence_score(
        [],
        pathway_count=0,
        biomarker_count=0,
        has_mechanism=False,
        target_count=0,
        safety_data_available=False,
        current_year=2026,
    )
    assert level == EvidenceConfidenceLevel.LOW
    assert numeric < 0.45


def test_classify_negative_from_abstract():
    snippet = _snippet(
        "n1",
        StudyType.RCT,
        0.6,
        abstract="The intervention showed no significant improvement versus placebo.",
    )
    assert classify_study_outcome(snippet) == "negative"


def test_classify_positive_from_quality():
    snippet = _snippet("p1", StudyType.RCT, 0.7)
    assert classify_study_outcome(snippet) == "positive"