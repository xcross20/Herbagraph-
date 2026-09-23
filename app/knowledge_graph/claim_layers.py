"""Evidence claim layers.

Kernel claims may create recommendation cards.
Growth claims (pmid_growth_batch / generated_pmid_claims) may attach as
supporting literature only. They must never author a discuss/primary card.

Longtail curated batches stay card-eligible until a later promotion PR
splits them; they are tagged so audits can see the seam.
"""

from __future__ import annotations

LAYER_KERNEL = "kernel"
LAYER_LONGTAIL = "curated_longtail"
LAYER_GROWTH = "growth"

CARD_ELIGIBLE_LAYERS = frozenset({LAYER_KERNEL, LAYER_LONGTAIL})


def layer_of(claim: dict) -> str:
    raw = claim.get("source_layer")
    if raw in {LAYER_KERNEL, LAYER_LONGTAIL, LAYER_GROWTH}:
        return raw
    return LAYER_KERNEL


def is_growth_claim(claim: dict) -> bool:
    return layer_of(claim) == LAYER_GROWTH


def eligible_for_recommendation_card(claim: dict) -> bool:
    """True when this claim may introduce an intervention onto a report."""
    return layer_of(claim) in CARD_ELIGIBLE_LAYERS


def ensure_growth_tagged() -> None:
    """Idempotent. Generated rows are shared list items inside TIER_A."""
    from app.knowledge_graph.generated_pmid_claims import GENERATED_PMID_CLAIMS

    tag_claims(GENERATED_PMID_CLAIMS, LAYER_GROWTH)


def card_eligible_claims(claims: list[dict]) -> list[dict]:
    ensure_growth_tagged()
    return [c for c in claims if eligible_for_recommendation_card(c)]


def tag_claims(claims: list[dict], layer: str) -> list[dict]:
    """Annotate claims in place and return the same list."""
    for claim in claims:
        claim["source_layer"] = layer
        if layer == LAYER_GROWTH:
            claim["recommendation_intent"] = "context_only"
    return claims
