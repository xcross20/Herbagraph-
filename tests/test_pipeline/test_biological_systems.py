"""Unit tests for app.pipeline.biological_systems: the 16-pathway -> 7-system rollup."""

import pytest

from app.knowledge_graph.seed_data import PATHWAYS
from app.models.enums import PathwayDirection
from app.pipeline.biological_systems import (
    SIGNAL_LABELS,
    SYSTEM_NAMES,
    SYSTEM_PATHWAYS,
    compute_biological_systems,
)
from app.schemas.pipeline import PathwayActivation

pytestmark = pytest.mark.unit


def make_activation(pathway_code, activation_score, direction=PathwayDirection.ACTIVATED, biomarkers=None):
    return PathwayActivation(
        pathway_code=pathway_code,
        pathway_name=f"{pathway_code} name",
        activation_score=activation_score,
        direction=direction,
        contributing_biomarkers=biomarkers or ["SomeBiomarker"],
    )


def by_system(systems, code):
    return next(s for s in systems if s["system_code"] == code)


# ---------------------------------------------------------------------------
# Structural sanity
# ---------------------------------------------------------------------------


def test_exactly_7_systems():
    assert len(SYSTEM_PATHWAYS) == 7
    assert len(SYSTEM_NAMES) == 7


def test_every_internal_pathway_is_covered_by_at_least_one_system():
    all_pathway_codes = {p["code"] for p in PATHWAYS}
    covered = {code for codes in SYSTEM_PATHWAYS.values() for code in codes}
    assert all_pathway_codes == covered


def test_compute_biological_systems_always_returns_all_7():
    result = compute_biological_systems([])
    assert len(result) == 7
    assert all(s["signal_level"] == 0 for s in result)
    assert all(s["signal_label"] == "No Signal" for s in result)
    assert all(s["direction"] == "none" for s in result)
    assert all(s["confidence"] == "low" for s in result)
    assert all(s["drivers"] == [] for s in result)


def test_systems_sorted_by_signal_level_descending():
    activations = [make_activation("NF_KB", 0.9), make_activation("THYROID_HPT", 0.2)]
    result = compute_biological_systems(activations)
    levels = [s["signal_level"] for s in result]
    assert levels == sorted(levels, reverse=True)


# ---------------------------------------------------------------------------
# Signal level (0-3) scoring
# ---------------------------------------------------------------------------


def test_signal_level_0_when_no_matching_pathway():
    result = compute_biological_systems([])
    inflammation = by_system(result, "inflammation")
    assert inflammation["signal_level"] == 0


def test_signal_level_1_mild_for_low_activation_score():
    activations = [make_activation("NF_KB", 0.2, biomarkers=["CRP"])]
    result = compute_biological_systems(activations)
    inflammation = by_system(result, "inflammation")
    assert inflammation["signal_level"] == 1
    assert inflammation["signal_label"] == "Mild Signal"


def test_signal_level_2_moderate_for_mid_activation_score():
    activations = [make_activation("NF_KB", 0.5, biomarkers=["CRP"])]
    result = compute_biological_systems(activations)
    inflammation = by_system(result, "inflammation")
    assert inflammation["signal_level"] == 2
    assert inflammation["signal_label"] == "Moderate Signal"


def test_signal_level_3_strong_for_high_activation_score():
    activations = [make_activation("NF_KB", 0.9, biomarkers=["CRP"])]
    result = compute_biological_systems(activations)
    inflammation = by_system(result, "inflammation")
    assert inflammation["signal_level"] == 3
    assert inflammation["signal_label"] == "Strong Signal"


def test_multiple_supporting_biomarkers_bump_signal_level():
    single = compute_biological_systems([make_activation("NF_KB", 0.2, biomarkers=["CRP"])])
    multi = compute_biological_systems(
        [
            make_activation("NF_KB", 0.2, biomarkers=["CRP"]),
            make_activation("IL6_JAK_STAT3", 0.2, biomarkers=["Ferritin"]),
        ]
    )
    assert by_system(multi, "inflammation")["signal_level"] > by_system(single, "inflammation")["signal_level"]


def test_signal_level_capped_at_3():
    activations = [
        make_activation("NF_KB", 1.0, biomarkers=["CRP"]),
        make_activation("IL6_JAK_STAT3", 1.0, biomarkers=["Ferritin", "Homocysteine"]),
    ]
    result = compute_biological_systems(activations)
    assert by_system(result, "inflammation")["signal_level"] == 3


def test_all_signal_labels_have_string_values():
    assert set(SIGNAL_LABELS.keys()) == {0, 1, 2, 3}
    assert all(isinstance(v, str) for v in SIGNAL_LABELS.values())


# ---------------------------------------------------------------------------
# Direction (elevated / reduced / mixed / none)
# ---------------------------------------------------------------------------


def test_direction_elevated_when_only_activated():
    activations = [make_activation("NF_KB", 0.8, direction=PathwayDirection.ACTIVATED)]
    result = compute_biological_systems(activations)
    assert by_system(result, "inflammation")["direction"] == "elevated"


def test_direction_reduced_when_only_suppressed():
    activations = [make_activation("VITAMIN_D_RECEPTOR", 0.8, direction=PathwayDirection.SUPPRESSED)]
    result = compute_biological_systems(activations)
    assert by_system(result, "nutrient_status")["direction"] == "reduced"


def test_direction_mixed_when_both_present_in_same_system():
    activations = [
        make_activation("IRON_HEPCIDIN", 0.5, direction=PathwayDirection.ACTIVATED, biomarkers=["Ferritin"]),
        make_activation("VITAMIN_D_RECEPTOR", 0.5, direction=PathwayDirection.SUPPRESSED, biomarkers=["Vitamin D"]),
    ]
    result = compute_biological_systems(activations)
    assert by_system(result, "nutrient_status")["direction"] == "mixed"


def test_direction_none_when_no_signal():
    result = compute_biological_systems([])
    assert by_system(result, "inflammation")["direction"] == "none"


# ---------------------------------------------------------------------------
# Confidence (low / moderate / high)
# ---------------------------------------------------------------------------


def test_confidence_low_when_no_pathways():
    result = compute_biological_systems([])
    assert by_system(result, "inflammation")["confidence"] == "low"


def test_confidence_moderate_with_one_biomarker_and_moderate_score():
    activations = [make_activation("NF_KB", 0.4, biomarkers=["CRP"])]
    result = compute_biological_systems(activations)
    assert by_system(result, "inflammation")["confidence"] == "moderate"


def test_confidence_high_with_multiple_biomarkers_and_strong_score():
    activations = [
        make_activation("NF_KB", 0.9, biomarkers=["CRP"]),
        make_activation("IL6_JAK_STAT3", 0.7, biomarkers=["Ferritin"]),
    ]
    result = compute_biological_systems(activations)
    assert by_system(result, "inflammation")["confidence"] == "high"


# ---------------------------------------------------------------------------
# Drivers and nested pathway refs
# ---------------------------------------------------------------------------


def test_drivers_are_deduplicated_and_sorted():
    activations = [
        make_activation("NF_KB", 0.5, biomarkers=["CRP", "Ferritin"]),
        make_activation("IL6_JAK_STAT3", 0.5, biomarkers=["Ferritin"]),
    ]
    result = compute_biological_systems(activations)
    assert by_system(result, "inflammation")["drivers"] == ["CRP", "Ferritin"]


def test_pathways_nested_under_system_include_code_and_name():
    activations = [make_activation("NF_KB", 0.5, biomarkers=["CRP"])]
    result = compute_biological_systems(activations)
    inflammation = by_system(result, "inflammation")
    assert {"pathway_code": "NF_KB", "pathway_name": "NF_KB name"} in inflammation["pathways"]


def test_pathway_shared_across_two_systems_appears_in_both():
    # HEPATIC_LIPID informs both cardiovascular_risk and liver_detox_stress.
    activations = [make_activation("HEPATIC_LIPID", 0.7, biomarkers=["LDL"])]
    result = compute_biological_systems(activations)
    cv = by_system(result, "cardiovascular_risk")
    liver = by_system(result, "liver_detox_stress")
    assert cv["signal_level"] > 0
    assert liver["signal_level"] > 0
