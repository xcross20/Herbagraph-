"""Pure-data validation tests for app.knowledge_graph.food_seed_data.

No database or async fixtures needed.
"""

import pytest

from app.knowledge_graph.food_seed_data import (
    COMPOUND_TO_FOOD_SOURCES,
    FOOD_COMPOUND_EVIDENCE_CLAIMS,
    FOOD_COMPOUND_SOURCES,
    FOOD_INTERVENTIONS,
    FOOD_TO_COMPOUNDS,
    PHYTOCHEMICAL_COMPOUNDS,
)
from app.knowledge_graph.seed_data import PATHWAYS

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# PHYTOCHEMICAL_COMPOUNDS / FOOD_INTERVENTIONS
# ---------------------------------------------------------------------------


def test_phytochemical_compounds_count():
    assert len(PHYTOCHEMICAL_COMPOUNDS) == 8


def test_phytochemical_compounds_unique_names():
    names = [c["name"] for c in PHYTOCHEMICAL_COMPOUNDS]
    assert len(names) == len(set(names))


def test_food_interventions_count():
    assert len(FOOD_INTERVENTIONS) == 13


def test_food_interventions_unique_names():
    names = [f["name"] for f in FOOD_INTERVENTIONS]
    assert len(names) == len(set(names))


# ---------------------------------------------------------------------------
# FOOD_COMPOUND_SOURCES referential integrity
# ---------------------------------------------------------------------------


def test_food_compound_sources_foods_exist_in_food_interventions():
    food_names = {f["name"] for f in FOOD_INTERVENTIONS}
    for food, _compound, _richness, _serving, _note in FOOD_COMPOUND_SOURCES:
        assert food in food_names, f"unknown food {food!r} in FOOD_COMPOUND_SOURCES"


def test_food_compound_sources_compounds_exist_in_phytochemical_compounds():
    compound_names = {c["name"] for c in PHYTOCHEMICAL_COMPOUNDS}
    for _food, compound, _richness, _serving, _note in FOOD_COMPOUND_SOURCES:
        assert compound in compound_names, f"unknown compound {compound!r} in FOOD_COMPOUND_SOURCES"


def test_food_compound_sources_valid_richness():
    valid_richness = {"high", "moderate", "low"}
    for _food, _compound, richness, _serving, _note in FOOD_COMPOUND_SOURCES:
        assert richness in valid_richness


# ---------------------------------------------------------------------------
# COMPOUND_TO_FOOD_SOURCES / FOOD_TO_COMPOUNDS derived lookups
# ---------------------------------------------------------------------------


def test_compound_to_food_sources_sulforaphane():
    sulforaphane_sources = COMPOUND_TO_FOOD_SOURCES["Sulforaphane"]
    assert len(sulforaphane_sources) == 4
    foods = {entry["food"] for entry in sulforaphane_sources}
    assert "Broccoli Sprouts" in foods
    broccoli_sprouts_entry = next(e for e in sulforaphane_sources if e["food"] == "Broccoli Sprouts")
    assert broccoli_sprouts_entry["richness"] == "high"


def test_food_to_compounds_broccoli_sprouts():
    entries = FOOD_TO_COMPOUNDS["Broccoli Sprouts"]
    compounds = {entry["compound"] for entry in entries}
    assert "Sulforaphane" in compounds


def test_compound_to_food_sources_inverted_correctly():
    for food, compound, richness, serving, note in FOOD_COMPOUND_SOURCES:
        matches = [
            entry
            for entry in COMPOUND_TO_FOOD_SOURCES[compound]
            if entry["food"] == food
            and entry["richness"] == richness
            and entry["typical_serving"] == serving
            and entry["note"] == note
        ]
        assert len(matches) == 1, f"missing/duplicate inverted entry for ({food}, {compound})"


def test_food_to_compounds_inverted_correctly():
    for food, compound, richness, serving, note in FOOD_COMPOUND_SOURCES:
        matches = [
            entry
            for entry in FOOD_TO_COMPOUNDS[food]
            if entry["compound"] == compound
            and entry["richness"] == richness
            and entry["typical_serving"] == serving
            and entry["note"] == note
        ]
        assert len(matches) == 1, f"missing/duplicate inverted entry for ({food}, {compound})"


def test_lookup_dicts_total_entry_counts_match_sources():
    total_compound_entries = sum(len(v) for v in COMPOUND_TO_FOOD_SOURCES.values())
    total_food_entries = sum(len(v) for v in FOOD_TO_COMPOUNDS.values())
    assert total_compound_entries == len(FOOD_COMPOUND_SOURCES)
    assert total_food_entries == len(FOOD_COMPOUND_SOURCES)


# ---------------------------------------------------------------------------
# Safety-relevant spot checks called out in the README
# ---------------------------------------------------------------------------


def test_beta_carotene_smoking_contraindication():
    beta_carotene = next(c for c in PHYTOCHEMICAL_COMPOUNDS if c["name"] == "Beta-Carotene")
    smoking_flags = [f for f in beta_carotene["safety_flags"] if f["condition"] == "smoking"]
    assert len(smoking_flags) == 1
    assert smoking_flags[0]["severity"] == "contraindication"


def test_allicin_warfarin_interaction():
    allicin = next(c for c in PHYTOCHEMICAL_COMPOUNDS if c["name"] == "Allicin")
    warfarin_interactions = [d for d in allicin["drug_interactions"] if d["drug_name"] == "Warfarin"]
    assert len(warfarin_interactions) == 1


# ---------------------------------------------------------------------------
# FOOD_COMPOUND_EVIDENCE_CLAIMS referential integrity
# ---------------------------------------------------------------------------


def test_food_compound_evidence_claims_intervention_names_exist():
    compound_names = {c["name"] for c in PHYTOCHEMICAL_COMPOUNDS}
    for claim in FOOD_COMPOUND_EVIDENCE_CLAIMS:
        assert claim["intervention_name"] in compound_names, (
            f"unknown intervention_name {claim['intervention_name']!r} in food compound evidence claim"
        )


def test_food_compound_evidence_claims_pathway_codes_exist():
    pathway_codes = {p["code"] for p in PATHWAYS}
    for claim in FOOD_COMPOUND_EVIDENCE_CLAIMS:
        if claim["pathway_code"] is not None:
            assert claim["pathway_code"] in pathway_codes, (
                f"unknown pathway_code {claim['pathway_code']!r} in food compound evidence claim"
            )
