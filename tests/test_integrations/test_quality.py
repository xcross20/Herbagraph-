"""Unit tests for app.integrations.quality: classify_study_type and quality_score_for."""

import pytest

from app.integrations.quality import STUDY_TYPE_WEIGHTS, classify_study_type, quality_score_for
from app.models.enums import StudyType

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# classify_study_type: keyword detection, case-insensitive, title + pub types
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "title",
    [
        "A meta-analysis of curcumin trials",
        "A META-ANALYSIS of curcumin trials",
        "A meta analysis of curcumin trials",
        "A META ANALYSIS of curcumin trials",
    ],
)
def test_classify_detects_meta_analysis_in_title(title):
    assert classify_study_type(title) == StudyType.META_ANALYSIS


@pytest.mark.parametrize(
    "title",
    [
        "A systematic review of omega-3 supplementation",
        "A SYSTEMATIC REVIEW of omega-3 supplementation",
    ],
)
def test_classify_detects_systematic_review_in_title(title):
    assert classify_study_type(title) == StudyType.SYSTEMATIC_REVIEW


@pytest.mark.parametrize(
    "title",
    [
        "A randomized controlled trial of berberine",
        "A RANDOMIZED controlled trial of berberine",
        "A randomised controlled trial of berberine",
        "An RCT of berberine for glycemic control",
    ],
)
def test_classify_detects_rct_in_title(title):
    assert classify_study_type(title) == StudyType.RCT


@pytest.mark.parametrize(
    "title",
    [
        "A cohort study of vitamin D and mortality",
        "A COHORT study of vitamin D and mortality",
    ],
)
def test_classify_detects_cohort_in_title(title):
    assert classify_study_type(title) == StudyType.COHORT


@pytest.mark.parametrize(
    "title",
    [
        "A case-control study of ashwagandha use",
        "A case control study of ashwagandha use",
        "A CASE-CONTROL study of ashwagandha use",
    ],
)
def test_classify_detects_case_control_in_title(title):
    assert classify_study_type(title) == StudyType.CASE_CONTROL


def test_classify_falls_back_to_preclinical_for_unmatched_title():
    assert classify_study_type("Effects of curcumin on cultured hepatocytes") == StudyType.PRECLINICAL


def test_classify_falls_back_to_preclinical_for_empty_title_and_no_pub_types():
    assert classify_study_type("") == StudyType.PRECLINICAL


def test_classify_uses_publication_types_when_title_is_generic():
    assert (
        classify_study_type("Curcumin and inflammation", ["Meta-Analysis"]) == StudyType.META_ANALYSIS
    )


def test_classify_publication_types_case_insensitive():
    assert (
        classify_study_type("Curcumin and inflammation", ["RANDOMIZED CONTROLLED TRIAL"])
        == StudyType.RCT
    )


def test_classify_handles_none_publication_types():
    assert classify_study_type("Some preclinical title", None) == StudyType.PRECLINICAL


def test_classify_precedence_meta_analysis_over_rct():
    # Title mentions both "meta-analysis" and "randomized" -- meta-analysis wins (checked first).
    title = "A meta-analysis of randomized controlled trials of curcumin"
    assert classify_study_type(title) == StudyType.META_ANALYSIS


def test_classify_precedence_systematic_review_over_cohort():
    title = "A systematic review of cohort studies on omega-3"
    assert classify_study_type(title) == StudyType.SYSTEMATIC_REVIEW


def test_classify_precedence_rct_over_cohort():
    title = "A randomized cohort trial of berberine"
    assert classify_study_type(title) == StudyType.RCT


# ---------------------------------------------------------------------------
# quality_score_for
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "study_type, expected_weight",
    [
        (StudyType.META_ANALYSIS, 1.00),
        (StudyType.SYSTEMATIC_REVIEW, 0.90),
        (StudyType.RCT, 0.85),
        (StudyType.COHORT, 0.60),
        (StudyType.CASE_CONTROL, 0.45),
        (StudyType.PRECLINICAL, 0.20),
    ],
)
def test_quality_score_for_each_study_type(study_type, expected_weight):
    assert quality_score_for(study_type) == pytest.approx(expected_weight)


def test_quality_score_for_matches_weights_table_exactly():
    for study_type, weight in STUDY_TYPE_WEIGHTS.items():
        assert quality_score_for(study_type) == pytest.approx(weight)


def test_study_type_weights_covers_every_study_type_enum_member():
    assert set(STUDY_TYPE_WEIGHTS.keys()) == set(StudyType)


def test_quality_score_for_unknown_value_raises_key_error():
    with pytest.raises(KeyError):
        quality_score_for("not_a_real_study_type")
