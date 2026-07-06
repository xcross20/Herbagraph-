"""Unit tests for Stage 3: pathway_mapper.map_pathways.

Covers every biomarker/status rule in _PATHWAY_CONFIGS, severity multipliers,
score accumulation/capping, sorting, and contributing_biomarkers correctness.
"""

import pytest

from app.models.enums import LabResultStatus, PathwayDirection
from app.pipeline.pathway_mapper import _PATHWAY_CONFIGS, map_pathways
from app.schemas.pipeline import NormalizedLabResult

pytestmark = pytest.mark.unit


def make_lab(name: str, status: LabResultStatus, category: str | None = None, value: float = 1.0):
    return NormalizedLabResult(
        biomarker_name=name,
        raw_test_name=name,
        value=value,
        status=status,
        category=category,
    )


def activations_by_code(activations):
    return {a.pathway_code: a for a in activations}


# ---------------------------------------------------------------------------
# Rule table sanity
# ---------------------------------------------------------------------------


def test_rule_table_has_substantial_size():
    """README documents 50+ biomarker-to-pathway rules across the 25-biomarker panel."""
    assert len(_PATHWAY_CONFIGS) == 54


def test_rule_table_covers_25_biomarkers():
    biomarkers = {rule[0] for rule in _PATHWAY_CONFIGS}
    assert len(biomarkers) == 25


def test_rule_table_covers_16_pathway_codes():
    pathway_codes = {rule[2] for rule in _PATHWAY_CONFIGS}
    assert len(pathway_codes) == 16


# ---------------------------------------------------------------------------
# Per biomarker/status rule correctness (HIGH/LOW, multiplier == 1.0)
# ---------------------------------------------------------------------------

# (biomarker_name, status, {pathway_code: (weight, direction)})
_RULE_CASES = [
    ("CRP", LabResultStatus.HIGH, {
        "NF_KB": (0.9, PathwayDirection.ACTIVATED),
        "IL6_JAK_STAT3": (0.7, PathwayDirection.ACTIVATED),
    }),
    ("Homocysteine", LabResultStatus.HIGH, {
        "ONE_CARBON_METHYLATION": (0.9, PathwayDirection.SUPPRESSED),
        "NF_KB": (0.3, PathwayDirection.ACTIVATED),
    }),
    ("Glucose", LabResultStatus.HIGH, {
        "INSULIN_PI3K_AKT": (0.8, PathwayDirection.SUPPRESSED),
        "GLP1_INCRETINS": (0.5, PathwayDirection.SUPPRESSED),
        "AMPK": (0.4, PathwayDirection.SUPPRESSED),
    }),
    ("HbA1c", LabResultStatus.HIGH, {
        "INSULIN_PI3K_AKT": (0.9, PathwayDirection.SUPPRESSED),
        "GLP1_INCRETINS": (0.5, PathwayDirection.SUPPRESSED),
        "MITOCHONDRIAL_NAD": (0.3, PathwayDirection.SUPPRESSED),
        "NF_KB": (0.2, PathwayDirection.ACTIVATED),
    }),
    ("Insulin", LabResultStatus.HIGH, {
        "INSULIN_PI3K_AKT": (0.85, PathwayDirection.SUPPRESSED),
        "MTOR_AUTOPHAGY": (0.4, PathwayDirection.ACTIVATED),
    }),
    ("Uric Acid", LabResultStatus.HIGH, {
        "PURINE_URIC_ACID": (0.9, PathwayDirection.ACTIVATED),
        "NF_KB": (0.3, PathwayDirection.ACTIVATED),
        "RENAL_FILTRATION": (0.4, PathwayDirection.SUPPRESSED),
    }),
    ("LDL", LabResultStatus.HIGH, {
        "HEPATIC_LIPID": (0.9, PathwayDirection.ACTIVATED),
        "NRF2": (0.4, PathwayDirection.SUPPRESSED),
        "IL6_JAK_STAT3": (0.2, PathwayDirection.ACTIVATED),
    }),
    ("HDL", LabResultStatus.LOW, {
        "HEPATIC_LIPID": (0.6, PathwayDirection.SUPPRESSED),
        "NRF2": (0.3, PathwayDirection.SUPPRESSED),
    }),
    ("Triglycerides", LabResultStatus.HIGH, {
        "HEPATIC_LIPID": (0.85, PathwayDirection.ACTIVATED),
        "AMPK": (0.3, PathwayDirection.SUPPRESSED),
        "MITOCHONDRIAL_NAD": (0.2, PathwayDirection.SUPPRESSED),
    }),
    ("ALT", LabResultStatus.HIGH, {
        "HEPATIC_LIPID": (0.7, PathwayDirection.ACTIVATED),
        "NRF2": (0.5, PathwayDirection.SUPPRESSED),
    }),
    ("AST", LabResultStatus.HIGH, {
        "HEPATIC_LIPID": (0.6, PathwayDirection.ACTIVATED),
        "NRF2": (0.4, PathwayDirection.SUPPRESSED),
        "MITOCHONDRIAL_NAD": (0.3, PathwayDirection.SUPPRESSED),
    }),
    ("Vitamin D", LabResultStatus.LOW, {
        "VITAMIN_D_RECEPTOR": (0.9, PathwayDirection.SUPPRESSED),
    }),
    ("Vitamin D", LabResultStatus.HIGH, {
        "VITAMIN_D_RECEPTOR": (0.5, PathwayDirection.ACTIVATED),
    }),
    ("TSH", LabResultStatus.HIGH, {
        "THYROID_HPT": (0.8, PathwayDirection.SUPPRESSED),
        "HPA_AXIS": (0.3, PathwayDirection.ACTIVATED),
    }),
    ("TSH", LabResultStatus.LOW, {
        "THYROID_HPT": (0.8, PathwayDirection.ACTIVATED),
    }),
    ("B12", LabResultStatus.LOW, {
        "ONE_CARBON_METHYLATION": (0.8, PathwayDirection.SUPPRESSED),
    }),
    ("Folate", LabResultStatus.LOW, {
        "ONE_CARBON_METHYLATION": (0.85, PathwayDirection.SUPPRESSED),
    }),
    ("ApoB", LabResultStatus.HIGH, {
        "HEPATIC_LIPID": (0.9, PathwayDirection.ACTIVATED),
    }),
    ("GGT", LabResultStatus.HIGH, {
        "HEPATIC_LIPID": (0.5, PathwayDirection.ACTIVATED),
        "NRF2": (0.5, PathwayDirection.SUPPRESSED),
    }),
    ("Creatinine", LabResultStatus.HIGH, {
        "RENAL_FILTRATION": (0.85, PathwayDirection.SUPPRESSED),
    }),
    ("eGFR", LabResultStatus.LOW, {
        "RENAL_FILTRATION": (0.9, PathwayDirection.SUPPRESSED),
    }),
    ("Lp(a)", LabResultStatus.HIGH, {
        "HEPATIC_LIPID": (0.6, PathwayDirection.ACTIVATED),
    }),
    ("Free T3", LabResultStatus.LOW, {
        "THYROID_HPT": (0.7, PathwayDirection.SUPPRESSED),
    }),
    ("Free T4", LabResultStatus.LOW, {
        "THYROID_HPT": (0.7, PathwayDirection.SUPPRESSED),
    }),
    ("Cortisol", LabResultStatus.HIGH, {
        "HPA_AXIS": (0.8, PathwayDirection.ACTIVATED),
    }),
    ("Cortisol", LabResultStatus.LOW, {
        "HPA_AXIS": (0.6, PathwayDirection.SUPPRESSED),
    }),
    ("DHEA-S", LabResultStatus.LOW, {
        "HPA_AXIS": (0.4, PathwayDirection.SUPPRESSED),
    }),
    ("Ferritin", LabResultStatus.HIGH, {
        "IRON_HEPCIDIN": (0.85, PathwayDirection.ACTIVATED),
        "NF_KB": (0.3, PathwayDirection.ACTIVATED),
        "MITOCHONDRIAL_NAD": (0.3, PathwayDirection.SUPPRESSED),
    }),
    ("Ferritin", LabResultStatus.LOW, {
        "IRON_HEPCIDIN": (0.85, PathwayDirection.SUPPRESSED),
    }),
]


@pytest.mark.parametrize("biomarker, status, expected", _RULE_CASES)
def test_single_biomarker_rule_mapping(biomarker, status, expected):
    labs = [make_lab(biomarker, status)]
    result = map_pathways(labs)
    by_code = activations_by_code(result)

    assert set(by_code) == set(expected)
    for code, (weight, direction) in expected.items():
        activation = by_code[code]
        assert activation.direction == direction
        assert activation.activation_score == pytest.approx(weight)
        assert activation.contributing_biomarkers == [biomarker]


@pytest.mark.parametrize(
    "status",
    [LabResultStatus.NORMAL, LabResultStatus.OPTIMAL],
)
def test_normal_and_optimal_never_trigger_any_pathway(status):
    labs = [
        make_lab("CRP", status),
        make_lab("LDL", status),
        make_lab("Glucose", status),
        make_lab("Vitamin D", status),
    ]
    assert map_pathways(labs) == []


def test_abnormal_biomarker_without_matching_rule_produces_no_activation():
    # CRP has no rule for LOW status (only HIGH / CRITICAL_HIGH), even though LOW
    # is itself an "abnormal" status.
    labs = [make_lab("CRP", LabResultStatus.LOW)]
    assert map_pathways(labs) == []


def test_empty_input_returns_empty_list():
    assert map_pathways([]) == []


# ---------------------------------------------------------------------------
# Severity multiplier for critical statuses
# ---------------------------------------------------------------------------


def test_critical_high_applies_severity_multiplier_and_caps_at_one():
    labs = [make_lab("CRP", LabResultStatus.CRITICAL_HIGH)]
    result = map_pathways(labs)
    by_code = activations_by_code(result)

    # 0.9 * 1.3 = 1.17 -> capped to 1.0
    assert by_code["NF_KB"].activation_score == pytest.approx(1.0)
    # 0.7 * 1.3 = 0.91 -> under cap
    assert by_code["IL6_JAK_STAT3"].activation_score == pytest.approx(0.91)


def test_critical_low_applies_severity_multiplier():
    labs = [make_lab("Vitamin D", LabResultStatus.CRITICAL_LOW)]
    result = map_pathways(labs)
    by_code = activations_by_code(result)
    # 0.9 * 1.3 = 1.17 -> capped
    assert by_code["VITAMIN_D_RECEPTOR"].activation_score == pytest.approx(1.0)


def test_glucose_critical_high_adds_extra_renal_filtration_rule():
    """Glucose CRITICAL_HIGH triggers an additional RENAL_FILTRATION rule that
    plain HIGH does not."""
    high_result = map_pathways([make_lab("Glucose", LabResultStatus.HIGH)])
    critical_result = map_pathways([make_lab("Glucose", LabResultStatus.CRITICAL_HIGH)])

    high_codes = {a.pathway_code for a in high_result}
    critical_codes = {a.pathway_code for a in critical_result}

    assert "RENAL_FILTRATION" not in high_codes
    assert "RENAL_FILTRATION" in critical_codes

    critical_by_code = activations_by_code(critical_result)
    # 0.3 * 1.3 = 0.39
    assert critical_by_code["RENAL_FILTRATION"].activation_score == pytest.approx(0.39)
    # 0.8 * 1.3 = 1.04 -> capped
    assert critical_by_code["INSULIN_PI3K_AKT"].activation_score == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Accumulation across multiple biomarkers feeding the same pathway
# ---------------------------------------------------------------------------


def test_multiple_biomarkers_accumulate_into_same_pathway_and_cap_at_one():
    # All of these ACTIVATE NF_KB: CRP(0.9) + Homocysteine(0.3) + Uric Acid(0.3)
    # + Ferritin(0.3) + HbA1c(0.2) = 2.0 raw, capped to 1.0.
    labs = [
        make_lab("CRP", LabResultStatus.HIGH),
        make_lab("Homocysteine", LabResultStatus.HIGH),
        make_lab("Uric Acid", LabResultStatus.HIGH),
        make_lab("Ferritin", LabResultStatus.HIGH),
        make_lab("HbA1c", LabResultStatus.HIGH),
    ]
    result = map_pathways(labs)
    by_code = activations_by_code(result)

    nf_kb = by_code["NF_KB"]
    assert nf_kb.activation_score == pytest.approx(1.0)
    assert nf_kb.direction == PathwayDirection.ACTIVATED
    assert nf_kb.contributing_biomarkers == [
        "CRP",
        "Ferritin",
        "HbA1c",
        "Homocysteine",
        "Uric Acid",
    ]


def test_accumulation_without_cap_sums_weights_exactly():
    # CRP(0.9 ACT) + Homocysteine(0.3 ACT) = 1.2 raw... use just two contributors
    # whose sum is still under 1.0: Homocysteine(0.3) + HbA1c(0.2) + Uric Acid(0.3) = 0.8
    labs = [
        make_lab("Homocysteine", LabResultStatus.HIGH),
        make_lab("HbA1c", LabResultStatus.HIGH),
        make_lab("Uric Acid", LabResultStatus.HIGH),
    ]
    result = map_pathways(labs)
    by_code = activations_by_code(result)
    assert by_code["NF_KB"].activation_score == pytest.approx(0.8)


def test_mixed_direction_contributions_resolve_by_larger_net_score():
    # LDL HIGH activates HEPATIC_LIPID by 0.9; HDL LOW suppresses it by 0.6.
    # net_activated (0.9) >= net_suppressed (0.6) -> overall direction ACTIVATED.
    labs = [
        make_lab("LDL", LabResultStatus.HIGH),
        make_lab("HDL", LabResultStatus.LOW),
    ]
    result = map_pathways(labs)
    by_code = activations_by_code(result)

    hepatic = by_code["HEPATIC_LIPID"]
    assert hepatic.direction == PathwayDirection.ACTIVATED
    assert hepatic.activation_score == pytest.approx(0.9)
    assert hepatic.contributing_biomarkers == ["HDL", "LDL"]


def test_suppressed_direction_wins_when_net_suppressed_is_larger():
    # HDL LOW alone only suppresses HEPATIC_LIPID (no activation contribution).
    labs = [make_lab("HDL", LabResultStatus.LOW)]
    result = map_pathways(labs)
    by_code = activations_by_code(result)

    hepatic = by_code["HEPATIC_LIPID"]
    assert hepatic.direction == PathwayDirection.SUPPRESSED
    assert hepatic.activation_score == pytest.approx(0.6)


# ---------------------------------------------------------------------------
# Sorting and general invariants
# ---------------------------------------------------------------------------


def test_results_sorted_descending_by_activation_score():
    labs = [
        make_lab("CRP", LabResultStatus.HIGH),  # NF_KB 0.9, IL6_JAK_STAT3 0.7
        make_lab("Uric Acid", LabResultStatus.HIGH),  # PURINE_URIC_ACID 0.9, NF_KB 0.3, RENAL_FILTRATION 0.4
        make_lab("Vitamin D", LabResultStatus.HIGH),  # VITAMIN_D_RECEPTOR 0.5
    ]
    result = map_pathways(labs)
    scores = [a.activation_score for a in result]
    assert scores == sorted(scores, reverse=True)


def test_activation_score_never_exceeds_one_across_full_panel():
    # Feed every rule-referenced biomarker at once at CRITICAL severity so every
    # weight gets the 1.3x multiplier; nothing should ever exceed 1.0.
    biomarker_status_pairs = [
        ("CRP", LabResultStatus.CRITICAL_HIGH),
        ("Homocysteine", LabResultStatus.CRITICAL_HIGH),
        ("Glucose", LabResultStatus.CRITICAL_HIGH),
        ("HbA1c", LabResultStatus.CRITICAL_HIGH),
        ("Insulin", LabResultStatus.CRITICAL_HIGH),
        ("Uric Acid", LabResultStatus.CRITICAL_HIGH),
        ("LDL", LabResultStatus.CRITICAL_HIGH),
        ("HDL", LabResultStatus.CRITICAL_LOW),
        ("Triglycerides", LabResultStatus.CRITICAL_HIGH),
        ("ALT", LabResultStatus.CRITICAL_HIGH),
        ("AST", LabResultStatus.CRITICAL_HIGH),
        ("Vitamin D", LabResultStatus.CRITICAL_LOW),
        ("TSH", LabResultStatus.CRITICAL_HIGH),
        ("B12", LabResultStatus.CRITICAL_LOW),
        ("Folate", LabResultStatus.CRITICAL_LOW),
        ("Ferritin", LabResultStatus.CRITICAL_HIGH),
        ("ApoB", LabResultStatus.CRITICAL_HIGH),
        ("GGT", LabResultStatus.CRITICAL_HIGH),
        ("Creatinine", LabResultStatus.CRITICAL_HIGH),
        ("eGFR", LabResultStatus.CRITICAL_LOW),
        ("Lp(a)", LabResultStatus.CRITICAL_HIGH),
        ("Free T3", LabResultStatus.CRITICAL_LOW),
        ("Free T4", LabResultStatus.CRITICAL_LOW),
        ("Cortisol", LabResultStatus.CRITICAL_HIGH),
        ("DHEA-S", LabResultStatus.CRITICAL_LOW),
    ]
    labs = [make_lab(name, status) for name, status in biomarker_status_pairs]
    result = map_pathways(labs)
    assert len(result) > 0
    for activation in result:
        assert 0.0 <= activation.activation_score <= 1.0


def test_contributing_biomarkers_present_for_single_contributor_pathways():
    labs = [make_lab("Folate", LabResultStatus.LOW)]
    result = map_pathways(labs)
    by_code = activations_by_code(result)
    assert by_code["ONE_CARBON_METHYLATION"].contributing_biomarkers == ["Folate"]


def test_unrelated_biomarker_name_produces_no_activation():
    labs = [make_lab("Not A Real Biomarker", LabResultStatus.HIGH)]
    assert map_pathways(labs) == []
