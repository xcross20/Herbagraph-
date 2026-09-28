"""Metabolic identity uses the same transfer rules as magnesium and B12."""

from __future__ import annotations

import pytest

from app.discovery.composition import (
    claim_transfers,
    load_metabolic_graph,
    overlay_uses_existing_layers,
    unknown_form_stays_unknown,
)
from app.pipeline.metabolic_identity import (
    clinical_flags,
    explicitly_does_not_address,
    outcome_evidence_transfers,
    resolve_metabolic_code,
)

pytestmark = pytest.mark.unit


def test_overlay_does_not_invent_a_new_identity_layer():
    graph = load_metabolic_graph()
    from app.discovery.composition import load_metabolic_overlay

    assert overlay_uses_existing_layers(load_metabolic_overlay())
    assert resolve_metabolic_code("magnesium oxide") == "magnesium_oxide"
    assert claim_transfers("magnesium_oxide", "magnesium_glycinate", "supports_outcome_in_population", graph) is False


def test_goldenseal_does_not_inherit_berberine():
    assert resolve_metabolic_code("goldenseal") == "goldenseal"
    assert resolve_metabolic_code("berberine hcl") == "berberine"
    assert explicitly_does_not_address("goldenseal", "berberine") is True
    assert outcome_evidence_transfers("berberine", "goldenseal") is False
    assert outcome_evidence_transfers("goldenseal", "berberine") is False


def test_cassia_is_not_ceylon_and_bare_cinnamon_stays_unknown():
    assert resolve_metabolic_code("cassia") == "cinnamon_cassia"
    assert resolve_metabolic_code("ceylon cinnamon") == "cinnamon_ceylon"
    assert resolve_metabolic_code("cinnamon") == "unknown_cinnamon_product"
    assert unknown_form_stays_unknown("unknown_cinnamon_product", load_metabolic_graph()) is True
    assert clinical_flags("cinnamon_cassia")["coumarin_bearing"] is True
    assert clinical_flags("cinnamon_ceylon")["coumarin_bearing"] is False
    assert explicitly_does_not_address("cinnamon_cassia", "cinnamon_ceylon") is True
    assert explicitly_does_not_address("unknown_cinnamon_product", "cinnamon_cassia") is True
    assert outcome_evidence_transfers("cinnamon_cassia", "cinnamon_ceylon") is False


def test_monacolin_measurement_does_not_become_every_ryr_product():
    graph = load_metabolic_graph()
    assert resolve_metabolic_code("red yeast rice") == "red_yeast_rice"
    assert resolve_metabolic_code("monacolin") == "monacolin_k"
    assert clinical_flags("red_yeast_rice")["pharmacologic_analogue"] == "statin"
    assert claim_transfers("monacolin_k", "red_yeast_rice", "contains_measured", graph) is False
    assert explicitly_does_not_address("unknown_ryr_product", "monacolin_k") is True
    assert unknown_form_stays_unknown("unknown_ryr_product", graph) is True


def test_food_first_forms_keep_their_own_codes():
    assert resolve_metabolic_code("psyllium husk") == "psyllium_husk"
    assert clinical_flags("psyllium_husk")["food_first"] is True
    assert resolve_metabolic_code("evoo") == "extra_virgin_olive_oil"
    assert resolve_metabolic_code("olive leaf") == "olive_leaf"
    assert resolve_metabolic_code("fish oil") == "omega_3"
