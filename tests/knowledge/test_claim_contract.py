"""M02: a claim either has the fields a card requires, or it cannot author one."""

from __future__ import annotations

import pytest

from app.knowledge_graph.claim_contract import (
    IndicationFamily,
    claim_from_legacy,
    family_for_biomarker,
)
from app.knowledge_graph.claim_layers import LAYER_GROWTH, ensure_growth_tagged
from app.knowledge_graph.generated_pmid_claims import GENERATED_PMID_CLAIMS

pytestmark = pytest.mark.unit


def test_ldl_is_lipid_family():
    assert family_for_biomarker("LDL") is IndicationFamily.LIPID
    assert family_for_biomarker("HbA1c") is IndicationFamily.GLYCEMIC
    assert family_for_biomarker("ALT") is IndicationFamily.HEPATIC
    assert family_for_biomarker("Ferritin") is IndicationFamily.OTHER


def test_growth_legacy_row_cannot_author_card_even_if_marked_primary():
    ensure_growth_tagged()
    row = dict(GENERATED_PMID_CLAIMS[0])
    row["recommendation_intent"] = "primary"
    row["biomarker_name"] = "LDL"
    claim = claim_from_legacy(row, population="adults with elevated LDL")
    assert claim.layer.value == LAYER_GROWTH
    assert claim.recommendation_intent == "context_only"
    assert claim.can_author_card is False


def test_kernel_claim_missing_population_cannot_author_card():
    claim = claim_from_legacy(
        {
            "intervention_name": "Psyllium",
            "preparation": "husk",
            "biomarker_name": "LDL",
            "recommendation_intent": "primary",
            "source_layer": "kernel",
            "pmid": "123",
        },
        population="",
    )
    assert claim.can_author_card is False


def test_complete_kernel_claim_can_author_card():
    claim = claim_from_legacy(
        {
            "intervention_name": "Psyllium",
            "preparation": "husk",
            "biomarker_name": "LDL",
            "recommendation_intent": "primary",
            "source_layer": "kernel",
            "pmid": "123",
        },
        population="adults with elevated LDL",
    )
    assert claim.can_author_card is True
    assert claim.measurement.family is IndicationFamily.LIPID
    assert claim.intervention.preparation == "husk"
