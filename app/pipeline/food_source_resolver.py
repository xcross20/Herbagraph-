"""Resolve whole-food sources for interventions via the compound layer."""

from __future__ import annotations

from app.knowledge_graph.food_seed_data import COMPOUND_TO_FOOD_SOURCES, FOOD_TO_COMPOUNDS
from app.knowledge_graph.herb_catalog import HERB_INTERVENTIONS
from app.schemas.evidence import FoodSourceRead

_RICHNESS_ORDER = {"high": 0, "moderate": 1, "low": 2}

# Herbs/foods whose evidence name differs from the phytochemical food-compound key.
_MANUAL_COMPOUND_BRIDGE: dict[str, str] = {
    "Curcumin": "Curcumin",
    "Garlic": "Allicin",
    "Garlic Extract": "Allicin",
    "Turmeric": "Curcumin",
    "Turmeric Root": "Curcumin",
    "Green Tea": "EGCG",
    "Milk Thistle": "Silymarin",
    "Milk Thistle Seed": "Silymarin",
    "Blueberries": "Anthocyanins",
    "Pomegranate": "Ellagic Acid",
    "Cooked Tomatoes": "Lycopene",
    "Onions": "Quercetin",
}

_HERB_BY_NAME: dict[str, dict] = {h["name"]: h for h in HERB_INTERVENTIONS}


def _normalize_compound_name(name: str) -> str:
    """Strip parenthetical qualifiers for catalog matching."""
    if "(" in name:
        return name.split("(", 1)[0].strip()
    return name.strip()


def resolve_food_compound(intervention_name: str, category: str) -> str | None:
    """Return the phytochemical key used to look up whole-food sources."""
    if intervention_name in COMPOUND_TO_FOOD_SOURCES:
        return intervention_name

    bridged = _MANUAL_COMPOUND_BRIDGE.get(intervention_name)
    if bridged and bridged in COMPOUND_TO_FOOD_SOURCES:
        return bridged

    if category == "food":
        entries = FOOD_TO_COMPOUNDS.get(intervention_name, [])
        if entries:
            top = min(
                entries,
                key=lambda e: _RICHNESS_ORDER.get(
                    e["richness"].value if hasattr(e["richness"], "value") else str(e["richness"]),
                    9,
                ),
            )
            compound = top["compound"]
            if compound in COMPOUND_TO_FOOD_SOURCES:
                return compound

    herb = _HERB_BY_NAME.get(intervention_name)
    if herb:
        for compound_entry in herb.get("compounds", []):
            raw_name = compound_entry["name"]
            candidates = [raw_name, _normalize_compound_name(raw_name)]
            for candidate in candidates:
                if candidate in COMPOUND_TO_FOOD_SOURCES:
                    return candidate

    return None


def attach_food_sources(
    intervention_name: str,
    category: str,
) -> tuple[list[FoodSourceRead] | None, str | None]:
    """Return (food sources, linked phytochemical name) for a recommendation."""
    compound = resolve_food_compound(intervention_name, category)
    if not compound:
        return None, None
    sources = COMPOUND_TO_FOOD_SOURCES.get(compound)
    if not sources:
        return None, None
    return [FoodSourceRead(**s) for s in sources], compound