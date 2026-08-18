"""Issue 58 Slice C: literature claim cards. Never invent PMIDs."""

from __future__ import annotations

from app.discovery.composition import source_by_id
from app.discovery.scientific_output import SAFE_LIMITATION, ScientificItem, validate_scientific_output
from app.models.enums import ScientificItemType


def claim_cards_enabled() -> bool:
    from app.config import get_settings

    return bool(getattr(get_settings(), "literature_claim_cards_v1", False))


def build_claim_card(*, statement: str, source_id: str, claim_type: str = "limitation") -> dict:
    source = source_by_id(source_id)
    if source is None:
        return {
            "accepted": False,
            "statement": SAFE_LIMITATION,
            "source_id": source_id,
            "violations": ["citation_unresolved"],
        }
    check = validate_scientific_output(
        [
            ScientificItem(
                id=source_id,
                version="1",
                item_type=ScientificItemType.LITERATURE_CLAIM,
                statement=statement,
                provenance=[source_id, source.get("url") or ""],
            )
        ],
        stored_pmids=set(),
    )
    if not check.accepted:
        return {
            "accepted": False,
            "statement": check.replacement or SAFE_LIMITATION,
            "source_id": source_id,
            "violations": check.violations,
        }
    return {
        "accepted": True,
        "statement": statement,
        "source_id": source["id"],
        "title": source.get("title"),
        "url": source.get("url"),
        "claim_type": claim_type,
        "violations": [],
    }


STORED_CARDS = (
    {
        "families": frozenset({"grape", "food_composition"}),
        "statement": "Grape phenolic composition varies by variety, tissue, and processing; color is not a dose.",
        "source_id": "pmc:8567006",
        "claim_type": "limitation",
    },
    {
        "families": frozenset({"salt", "food_composition"}),
        "statement": "A measured pink-salt batch cannot be generalized to every product sharing that marketing label.",
        "source_id": "pmc:7603209",
        "claim_type": "limitation",
    },
)


def cards_for_next_steps(family_ids: list[str] | None = None) -> list[dict]:
    """Only stored fixture sources that support the displayed families. No live LLM titles."""
    wanted = {str(item) for item in (family_ids or []) if item}
    cards = []
    for item in STORED_CARDS:
        if wanted and item["families"].isdisjoint(wanted):
            continue
        card = build_claim_card(
            statement=item["statement"],
            source_id=item["source_id"],
            claim_type=item["claim_type"],
        )
        card["families"] = sorted(item["families"])
        cards.append(card)
    if family_ids is None:
        return cards
    return cards
