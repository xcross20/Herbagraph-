"""Derived food <-> compound lookups."""

from app.knowledge_graph.food_compound_links import FOOD_COMPOUND_SOURCES


def _build_compound_to_food_sources() -> dict[str, list[dict]]:
    lookup: dict[str, list[dict]] = {}
    for food, compound, richness, serving, note in FOOD_COMPOUND_SOURCES:
        lookup.setdefault(compound, []).append(
            {"food": food, "richness": richness, "typical_serving": serving, "note": note}
        )
    return lookup


def _build_food_to_compounds() -> dict[str, list[dict]]:
    lookup: dict[str, list[dict]] = {}
    for food, compound, richness, serving, note in FOOD_COMPOUND_SOURCES:
        lookup.setdefault(food, []).append(
            {"compound": compound, "richness": richness, "typical_serving": serving, "note": note}
        )
    return lookup


COMPOUND_TO_FOOD_SOURCES: dict[str, list[dict]] = _build_compound_to_food_sources()
FOOD_TO_COMPOUNDS: dict[str, list[dict]] = _build_food_to_compounds()
