"""Growth PMID rows may support context. They must not author a recommendation card."""

from __future__ import annotations

import pytest

from app.knowledge_graph.claim_layers import (
    LAYER_GROWTH,
    card_eligible_claims,
    eligible_for_recommendation_card,
    ensure_growth_tagged,
    tag_claims,
)
from app.knowledge_graph.generated_pmid_claims import GENERATED_PMID_CLAIMS
from app.models.enums import RecommendationIntent
from app.pipeline.catalog_evidence import _all_catalog_claims
from app.pipeline.intervention_catalog import _all_evidence_claims
pytestmark = pytest.mark.unit

_SYNTHETIC = "Synthetic Growth Only Herb"


def test_every_generated_pmid_row_is_context_only():
    ensure_growth_tagged()
    assert GENERATED_PMID_CLAIMS, "quarantine is meaningless if the growth corpus is empty"
    for claim in GENERATED_PMID_CLAIMS:
        assert claim.get("source_layer") == LAYER_GROWTH
        assert claim.get("recommendation_intent") == RecommendationIntent.CONTEXT_ONLY.value
        assert eligible_for_recommendation_card(claim) is False


def test_generated_name_cannot_enter_card_claim_sets():
    ensure_growth_tagged()
    growth_names = {c["intervention_name"] for c in GENERATED_PMID_CLAIMS}
    for claim in _all_catalog_claims() + _all_evidence_claims():
        if claim.get("intervention_name") in growth_names and claim.get("source_layer") == LAYER_GROWTH:
            pytest.fail(f"growth claim entered a card set: {claim['intervention_name']}")


def test_hostile_primary_growth_claim_cannot_win_card_intent():
    """A growth row born as primary must be rewritten and dropped from the card set."""
    hostile = {
        "intervention_name": _SYNTHETIC,
        "biomarker_name": "LDL Cholesterol",
        "pathway_code": "HEPATIC_LIPID",
        "effect": "decreases",
        "evidence_level": "high",
        "pmid": "00000000",
        "recommendation_intent": RecommendationIntent.PRIMARY.value,
        "summary": "Hostile fixture. Must not become a discuss card.",
    }
    kernel = {
        "intervention_name": "Kernel Iron",
        "recommendation_intent": RecommendationIntent.PRIMARY.value,
        "source_layer": "kernel",
    }
    tag_claims([hostile], LAYER_GROWTH)
    assert hostile["recommendation_intent"] == RecommendationIntent.CONTEXT_ONLY.value
    ranked = card_eligible_claims([hostile, kernel])
    assert [row["intervention_name"] for row in ranked] == ["Kernel Iron"]


def test_no_growth_row_survives_into_routing_or_catalog_cards():
    """Fails if card builders stop filtering source_layer=growth."""
    ensure_growth_tagged()
    leaked = [
        f"{claim['intervention_name']}:{claim.get('pmid')}"
        for claim in [*_all_catalog_claims(), *_all_evidence_claims()]
        if claim.get("source_layer") == LAYER_GROWTH
    ]
    assert leaked == []
