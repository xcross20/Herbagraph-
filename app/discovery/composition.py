"""Issue 60: general substance/food/form/assay identity. Not a catalog dump."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

GRAPH_PATH = Path(__file__).resolve().parent / "data" / "composition_graph_v1.json"

INHERITANCE_FORBIDDEN = frozenset(
    {
        "supports_outcome_in_population",
        "contains_measured",
    }
)


@lru_cache(maxsize=2)
def load_composition_graph(path: str | None = None) -> dict:
    return json.loads((Path(path) if path else GRAPH_PATH).read_text(encoding="utf-8"))


def concept(code: str) -> dict | None:
    for item in load_composition_graph().get("concepts") or []:
        if item["code"] == code:
            return item
    return None


def relations_from(code: str) -> list[dict]:
    return [row for row in load_composition_graph().get("relations") or [] if row["from"] == code]


def claim_transfers(source_code: str, target_code: str, relation: str) -> bool:
    """A parent/child label never silently inherits measured or outcome claims."""
    if source_code == target_code:
        return True
    if relation in INHERITANCE_FORBIDDEN:
        return False
    src = concept(source_code) or {}
    dst = concept(target_code) or {}
    if src.get("layer") == "product_batch" and dst.get("layer") != "product_batch":
        return False
    if src.get("layer") == "preparation" and dst.get("layer") in {"phenotype", "concept"}:
        return False
    for row in relations_from(source_code):
        if row["to"] == target_code and row["relation"] == "does_not_address":
            return False
    return False


def unknown_form_stays_unknown(product_code: str) -> bool:
    item = concept(product_code) or {}
    return item.get("layer") == "product_batch" and "unknown" in product_code


def assay_does_not_close_parent(assay_code: str, parent_code: str) -> bool:
    for row in relations_from(assay_code):
        if row["to"] == parent_code and row["relation"] == "partially_assesses":
            return True
    return False


def source_by_id(source_id: str) -> dict | None:
    for item in load_composition_graph().get("sources") or []:
        if item["id"] == source_id:
            return item
    return None
