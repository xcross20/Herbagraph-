"""Issue 58 Slice C: literature claim cards. Never invent PMIDs."""

from __future__ import annotations

from app.discovery.composition import source_by_id, source_is_example_seed
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
    eligible = not source_is_example_seed(source)
    return {
        "accepted": True,
        "statement": statement,
        "source_id": source["id"],
        "title": source.get("title"),
        "url": source.get("url"),
        "claim_type": claim_type,
        "role": source.get("role") or "stored",
        "eligible_for_case": eligible,
        "violations": [] if eligible else ["example_seed"],
    }


STORED_CARDS = (
    {
        "id": "claim-grape-composition",
        "families": frozenset({"grape"}),
        "triggers": ("grape", "vitis"),
        "statement": "Grape phenolic composition varies by variety, tissue, and processing; color is not a dose.",
        "source_id": "pmc:8567006",
        "claim_type": "limitation",
        "provenance_class": "example_seed",
    },
    {
        "id": "claim-salt-batch",
        "families": frozenset({"salt"}),
        "triggers": ("pink salt", "pink-salt", "himalayan salt", "rock salt"),
        "statement": "A measured pink-salt batch cannot be generalized to every product sharing that marketing label.",
        "source_id": "pmc:7603209",
        "claim_type": "limitation",
        "provenance_class": "example_seed",
    },
)

SEED_TITLES = frozenset({"grape bioactive composition review", "pink-salt composition analysis"})


def _blob(facts: dict | None, extra: str = "") -> str:
    parts = [extra]
    for key, value in (facts or {}).items():
        parts.append(str(key))
        parts.append(str(value))
    return " ".join(parts).lower()


def _reject(reason: str, source_id: str = "") -> dict:
    from app.discovery.telemetry import increment

    increment(f"citation_rejected_{reason}")
    return {
        "accepted": False,
        "statement": "Relevant literature is not yet available for the selected claim.",
        "source_id": source_id,
        "title": None,
        "violations": [reason],
        "reject_reason": reason,
    }


def cards_for_next_steps(
    family_ids: list[str] | None = None,
    *,
    facts: dict | None = None,
    text: str = "",
    active_claim_ids: list[str] | None = None,
) -> list[dict]:
    """Claim-driven cards only. Ontology example seeds never fill an unrelated Case."""
    wanted = {str(item) for item in (family_ids or []) if item}
    claims = {str(item) for item in (active_claim_ids or []) if item}
    haystack = _blob(facts, text)
    cards: list[dict] = []
    if not wanted and not claims and not haystack.strip():
        return [_reject("no_active_claim")]
    for item in STORED_CARDS:
        if item.get("provenance_class") == "example_seed":
            exposed = any(trigger in haystack for trigger in item["triggers"])
            claimed = bool(claims & {item["id"], *item["families"]})
            family_hit = bool(wanted & item["families"])
            if not (exposed and claimed and family_hit):
                reason = "example_seed" if not claimed else "context_mismatch"
                _reject(reason, item["source_id"])
                continue
        elif wanted and item["families"].isdisjoint(wanted):
            _reject("context_mismatch", item["source_id"])
            continue
        card = build_claim_card(
            statement=item["statement"],
            source_id=item["source_id"],
            claim_type=item["claim_type"],
        )
        card["families"] = sorted(item["families"])
        card["claim_id"] = item["id"]
        card["provenance_class"] = item.get("provenance_class") or "stored_claim"
        if item.get("provenance_class") == "example_seed" or not card.get("eligible_for_case"):
            card["eligible_for_case"] = False
        if not card.get("accepted"):
            _reject("entailment_failed", item["source_id"])
        cards.append(card)
    return [item for item in cards if item.get("accepted") and item.get("eligible_for_case") is not False]


def is_seed_literature(item: dict) -> bool:
    title = str(item.get("title") or "").strip().lower()
    source = str(item.get("source_id") or item.get("pmid") or "")
    return title in SEED_TITLES or source in {"pmc:8567006", "pmc:7603209"}
