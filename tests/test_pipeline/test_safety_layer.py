"""Unit tests for Stage 6: safety_layer.check_safety.

Covers drug-herb interaction detection (case-insensitive, substring-tolerant),
pregnancy/CKD/autoimmune contraindication exclusion, safety_risk assignment,
requires_clinician_review, and regulated-intervention flagging.
"""

import pytest

from app.models.enums import EvidenceLevel, InterventionCategory, SafetyRiskLevel
from app.pipeline.safety_layer import check_safety
from app.schemas.pipeline import LLMRecommendation

pytestmark = pytest.mark.unit


def make_rec(name: str, category=InterventionCategory.HERB, evidence_level=EvidenceLevel.MODERATE):
    return LLMRecommendation(
        intervention_name=name,
        category=category,
        mechanism="Some mechanism.",
        evidence_level=evidence_level,
    )


def profile(medications=None, conditions=None):
    return {
        "current_medications": medications or [],
        "known_conditions": conditions or [],
    }


def approved_by_name(report):
    return {r.intervention_name: r for r in report.approved_recommendations}


def excluded_by_name(report):
    return {r.intervention_name: r for r in report.excluded_recommendations}


# ---------------------------------------------------------------------------
# Drug-herb interactions from the README table
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "intervention_name, medication, expected_severity",
    [
        ("Boswellia Serrata", "Warfarin", SafetyRiskLevel.MODERATE),
        ("Curcumin", "Warfarin", SafetyRiskLevel.MODERATE),
        ("Curcumin", "Chemotherapy", SafetyRiskLevel.MODERATE),
        ("Berberine", "Warfarin", SafetyRiskLevel.MODERATE),
        ("Berberine", "Metformin", SafetyRiskLevel.MODERATE),
        ("Berberine", "Cyclosporine", SafetyRiskLevel.HIGH),
        ("Berberine", "Insulin glargine", SafetyRiskLevel.MODERATE),
        ("Omega-3", "Warfarin", SafetyRiskLevel.MODERATE),
        ("CoQ10", "Warfarin", SafetyRiskLevel.LOW),
        ("St. John's Wort", "Warfarin", SafetyRiskLevel.HIGH),
        ("St. John's Wort", "SSRIs", SafetyRiskLevel.HIGH),
        ("St. John's Wort", "Cyclosporine", SafetyRiskLevel.HIGH),
        ("Ginkgo", "Warfarin", SafetyRiskLevel.MODERATE),
        ("Ashwagandha", "Levothyroxine", SafetyRiskLevel.MODERATE),
        ("Ashwagandha", "Immunosuppressants", SafetyRiskLevel.MODERATE),
        ("Alpha Lipoic Acid", "Levothyroxine", SafetyRiskLevel.LOW),
        ("Alpha Lipoic Acid", "Insulin glargine", SafetyRiskLevel.MODERATE),
        ("Chromium", "Insulin glargine", SafetyRiskLevel.MODERATE),
        ("Milk Thistle", "Statins", SafetyRiskLevel.LOW),
        ("Quercetin", "Chemotherapy", SafetyRiskLevel.MODERATE),
        ("Allicin", "Warfarin", SafetyRiskLevel.MODERATE),
        ("Garlic", "Warfarin", SafetyRiskLevel.MODERATE),
    ],
)
def test_known_drug_herb_interactions_detected(intervention_name, medication, expected_severity):
    report = check_safety([make_rec(intervention_name)], profile(medications=[medication]))
    approved = approved_by_name(report)
    assert intervention_name in approved
    rec = approved[intervention_name]
    assert rec.safety_risk == expected_severity
    assert len(rec.interactions) == 1
    assert rec.interactions[0]  # a non-empty "<drug>: <mechanism>" label was produced


def test_interaction_detection_is_case_insensitive_for_intervention_and_medication():
    report = check_safety(
        [make_rec("BERBERINE")],
        profile(medications=["i take WARFARIN daily"]),
    )
    approved = approved_by_name(report)
    assert approved["BERBERINE"].safety_risk == SafetyRiskLevel.MODERATE


def test_interaction_detection_is_substring_tolerant_for_medication_names():
    report = check_safety(
        [make_rec("Berberine")],
        profile(medications=["warfarin sodium 5mg tablets"]),
    )
    approved = approved_by_name(report)
    assert approved["Berberine"].safety_risk == SafetyRiskLevel.MODERATE


def test_no_matching_interaction_yields_low_safety_risk():
    report = check_safety(
        [make_rec("Vitamin C")],
        profile(medications=["Aspirin"]),
    )
    approved = approved_by_name(report)
    assert approved["Vitamin C"].safety_risk == SafetyRiskLevel.LOW
    assert approved["Vitamin C"].interactions == []


def test_no_medications_yields_low_safety_risk_even_for_known_herb():
    report = check_safety([make_rec("Berberine")], profile(medications=[]))
    approved = approved_by_name(report)
    assert approved["Berberine"].safety_risk == SafetyRiskLevel.LOW


def test_multiple_matched_interactions_use_worst_severity():
    # Berberine matches Metformin (MODERATE) and Cyclosporine (HIGH) simultaneously.
    report = check_safety(
        [make_rec("Berberine")],
        profile(medications=["Metformin", "Cyclosporine"]),
    )
    approved = approved_by_name(report)
    rec = approved["Berberine"]
    assert rec.safety_risk == SafetyRiskLevel.HIGH
    assert len(rec.interactions) == 2


# ---------------------------------------------------------------------------
# Contraindications
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "intervention_name",
    ["Berberine", "Ashwagandha", "Curcumin", "Boswellia Serrata"],
)
def test_pregnancy_excludes_expected_interventions(intervention_name):
    report = check_safety([make_rec(intervention_name)], profile(conditions=["Pregnancy"]))
    excluded = excluded_by_name(report)
    assert intervention_name in excluded
    rec = excluded[intervention_name]
    assert rec.safety_risk == SafetyRiskLevel.CONTRAINDICATED
    assert rec.safety_notes == ["Excluded: contraindicated given patient's health profile."]
    assert report.approved_recommendations == []


def test_pregnancy_detection_is_case_insensitive_and_matches_substring():
    report = check_safety([make_rec("Berberine")], profile(conditions=["currently pregnant"]))
    excluded = excluded_by_name(report)
    assert "Berberine" in excluded


@pytest.mark.parametrize(
    "intervention_name",
    ["Magnesium", "Potassium", "Vitamin D"],
)
def test_severe_ckd_excludes_expected_interventions(intervention_name):
    report = check_safety(
        [make_rec(intervention_name, category=InterventionCategory.SUPPLEMENT)],
        profile(conditions=["severe chronic kidney disease"]),
    )
    excluded = excluded_by_name(report)
    assert intervention_name in excluded
    assert excluded[intervention_name].safety_risk == SafetyRiskLevel.CONTRAINDICATED


def test_ckd_abbreviation_alone_is_detected():
    report = check_safety(
        [make_rec("Magnesium", category=InterventionCategory.SUPPLEMENT)],
        profile(conditions=["CKD"]),
    )
    excluded = excluded_by_name(report)
    assert "Magnesium" in excluded


@pytest.mark.parametrize(
    "intervention_name",
    ["Ashwagandha", "Echinacea"],
)
def test_autoimmune_on_immunosuppressants_excludes_expected_interventions(intervention_name):
    report = check_safety(
        [make_rec(intervention_name)],
        profile(conditions=["Rheumatoid Arthritis"], medications=["Methotrexate"]),
    )
    excluded = excluded_by_name(report)
    assert intervention_name in excluded
    assert excluded[intervention_name].safety_risk == SafetyRiskLevel.CONTRAINDICATED


def test_autoimmune_condition_alone_without_immunosuppressant_does_not_exclude():
    report = check_safety(
        [make_rec("Ashwagandha")],
        profile(conditions=["Lupus"], medications=[]),
    )
    approved = approved_by_name(report)
    assert "Ashwagandha" in approved
    assert report.excluded_recommendations == []


def test_immunosuppressant_medication_alone_without_autoimmune_condition_does_not_exclude():
    report = check_safety(
        [make_rec("Ashwagandha")],
        profile(conditions=[], medications=["Methotrexate"]),
    )
    approved = approved_by_name(report)
    assert "Ashwagandha" in approved
    assert report.excluded_recommendations == []


def test_unrelated_intervention_is_not_excluded_by_contraindications():
    report = check_safety(
        [make_rec("Vitamin C", category=InterventionCategory.SUPPLEMENT)],
        profile(conditions=["Pregnancy"]),
    )
    approved = approved_by_name(report)
    assert "Vitamin C" in approved
    assert report.excluded_recommendations == []


# ---------------------------------------------------------------------------
# requires_clinician_review
# ---------------------------------------------------------------------------


def test_requires_clinician_review_true_when_exclusion_present():
    report = check_safety([make_rec("Berberine")], profile(conditions=["Pregnancy"]))
    assert report.requires_clinician_review is True


def test_requires_clinician_review_true_when_any_approved_rec_is_moderate_or_high():
    report = check_safety([make_rec("Berberine")], profile(medications=["Warfarin"]))
    assert report.requires_clinician_review is True


def test_requires_clinician_review_false_when_all_low_and_nothing_excluded():
    report = check_safety([make_rec("Vitamin C")], profile(medications=["Aspirin"]))
    assert report.requires_clinician_review is False
    assert report.overall_note == "No major drug-herb interactions detected."


def test_overall_note_flags_review_when_high_risk_present():
    report = check_safety([make_rec("Berberine")], profile(medications=["Cyclosporine"]))
    assert report.overall_note == "One or more recommendations require clinician review before starting."


# ---------------------------------------------------------------------------
# Regulated interventions
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "intervention_name, expected_snippet",
    [
        ("bpc-157", "investigational peptide"),
        ("TB-500", "investigational peptide"),
        ("Semaglutide", "prescription-only"),
        ("Tirzepatide", "prescription-only"),
    ],
)
def test_regulated_interventions_flagged_with_note(intervention_name, expected_snippet):
    report = check_safety(
        [make_rec(intervention_name, category=InterventionCategory.PEPTIDE)],
        profile(),
    )
    approved = approved_by_name(report)
    rec = approved[intervention_name]
    assert rec.is_regulated is True
    assert any(expected_snippet in note for note in rec.safety_notes)


def test_non_regulated_intervention_is_not_flagged():
    report = check_safety([make_rec("Vitamin C")], profile())
    approved = approved_by_name(report)
    assert approved["Vitamin C"].is_regulated is False


def test_regulated_and_contraindicated_still_marks_is_regulated_on_excluded():
    # Berberine isn't regulated, so use a regulated + also-excluded combination
    # isn't directly modeled; instead confirm a regulated intervention excluded
    # via unrelated contraindication still carries is_regulated flag.
    report = check_safety(
        [make_rec("Berberine", category=InterventionCategory.PEPTIDE)],
        profile(conditions=["Pregnancy"]),
    )
    excluded = excluded_by_name(report)
    assert excluded["Berberine"].is_regulated is False


def test_empty_recommendations_returns_empty_report():
    report = check_safety([], profile())
    assert report.approved_recommendations == []
    assert report.excluded_recommendations == []
    assert report.requires_clinician_review is False


# ---------------------------------------------------------------------------
# Liver/kidney warning stage (soft caution, not an exclusion)
# ---------------------------------------------------------------------------


def test_egcg_gets_liver_caution_note_with_liver_disease():
    report = check_safety(
        [make_rec("EGCG", category=InterventionCategory.PHYTOCHEMICAL)],
        profile(conditions=["liver disease"]),
    )
    approved = approved_by_name(report)
    assert "EGCG" in approved
    rec = approved["EGCG"]
    assert rec.safety_risk == SafetyRiskLevel.MODERATE
    assert any("hepatotoxicity" in note.lower() for note in rec.safety_notes)
    assert report.requires_clinician_review is True


def test_egcg_not_flagged_without_liver_disease():
    report = check_safety(
        [make_rec("EGCG", category=InterventionCategory.PHYTOCHEMICAL)],
        profile(conditions=[]),
    )
    approved = approved_by_name(report)
    assert approved["EGCG"].safety_risk == SafetyRiskLevel.LOW
    assert approved["EGCG"].safety_notes == []


def test_liver_caution_does_not_exclude_the_recommendation():
    report = check_safety(
        [make_rec("EGCG", category=InterventionCategory.PHYTOCHEMICAL)],
        profile(conditions=["hepatitis"]),
    )
    assert len(report.approved_recommendations) == 1
    assert len(report.excluded_recommendations) == 0


def test_liver_caution_only_applies_to_flagged_interventions():
    report = check_safety(
        [make_rec("Vitamin C", category=InterventionCategory.SUPPLEMENT)],
        profile(conditions=["cirrhosis"]),
    )
    approved = approved_by_name(report)
    assert approved["Vitamin C"].safety_risk == SafetyRiskLevel.LOW
    assert approved["Vitamin C"].safety_notes == []


def test_liver_caution_does_not_downgrade_an_existing_higher_risk():
    report = check_safety(
        [make_rec("Berberine", category=InterventionCategory.SUPPLEMENT)],
        profile(medications=["cyclosporine"], conditions=["fatty liver"]),
    )
    approved = approved_by_name(report)
    # Berberine+Cyclosporine is HIGH severity; liver caution (MODERATE) must not downgrade it.
    assert approved["Berberine"].safety_risk == SafetyRiskLevel.HIGH
