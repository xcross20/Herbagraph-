"""Merge hand-curated intervention entries over generated template catalogs by name."""

from __future__ import annotations


def merge_interventions(*catalogs: list[dict], curated: list[dict] | None = None) -> list[dict]:
    """Return a deduplicated intervention list; later catalogs and `curated` override earlier entries by name."""
    by_name: dict[str, dict] = {}
    for catalog in catalogs:
        for entry in catalog:
            by_name[entry["name"]] = entry
    if curated:
        for entry in curated:
            by_name[entry["name"]] = entry
    return list(by_name.values())


def merge_tuples(*sources: list[tuple]) -> list[tuple]:
    """Deduplicate (food, compound, ...) tuples; later sources win on duplicate keys."""
    seen: dict[tuple, tuple] = {}
    for source in sources:
        for row in source:
            key = (row[0], row[1])
            seen[key] = row
    return list(seen.values())