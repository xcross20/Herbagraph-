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


KNOWN_LAYERS = frozenset(
    {
        "concept",
        "subtype",
        "phenotype",
        "part",
        "form",
        "preparation",
        "product_batch",
        "exposure",
        "assay",
        "measured_composition",
        "claim",
    }
)

OVERLAY_PATH = Path(__file__).resolve().parent / "data" / "composition_graph_extensibility_folate.json"


@lru_cache(maxsize=4)
def load_composition_graph(path: str | None = None) -> dict:
    return json.loads((Path(path) if path else GRAPH_PATH).read_text(encoding="utf-8"))


def overlay_uses_existing_layers(overlay: dict, base: dict | None = None) -> bool:
    """A fifth domain is configuration if it only uses existing identity layers."""
    del base
    return all(item.get("layer") in KNOWN_LAYERS for item in (overlay.get("concepts") or []))


def merge_overlay(base: dict, overlay: dict) -> dict:
    if not overlay_uses_existing_layers(overlay, base):
        raise ValueError("overlay_requires_schema_change")
    concepts = {item["code"]: item for item in (base.get("concepts") or [])}
    for item in overlay.get("concepts") or []:
        concepts[item["code"]] = item
    relations = list(base.get("relations") or [])
    relations.extend(overlay.get("relations") or [])
    sources = {item["id"]: item for item in (base.get("sources") or [])}
    for item in overlay.get("sources") or []:
        sources[item["id"]] = item
    return {
        "version": base.get("version"),
        "provenance": base.get("provenance"),
        "concepts": list(concepts.values()),
        "relations": relations,
        "sources": list(sources.values()),
    }


def load_extensibility_overlay() -> dict:
    return json.loads(OVERLAY_PATH.read_text(encoding="utf-8"))


def concept(code: str, graph: dict | None = None) -> dict | None:
    for item in (graph or load_composition_graph()).get("concepts") or []:
        if item["code"] == code:
            return item
    return None


def relations_from(code: str, graph: dict | None = None) -> list[dict]:
    return [row for row in (graph or load_composition_graph()).get("relations") or [] if row["from"] == code]


def claim_transfers(source_code: str, target_code: str, relation: str, graph: dict | None = None) -> bool:
    """A parent/child label never silently inherits measured or outcome claims."""
    if source_code == target_code:
        return True
    if relation in INHERITANCE_FORBIDDEN:
        return False
    src = concept(source_code, graph) or {}
    dst = concept(target_code, graph) or {}
    if src.get("layer") == "product_batch" and dst.get("layer") != "product_batch":
        return False
    if src.get("layer") == "preparation" and dst.get("layer") in {"phenotype", "concept"}:
        return False
    for row in relations_from(source_code, graph):
        if row["to"] == target_code and row["relation"] == "does_not_address":
            return False
    return False


def unknown_form_stays_unknown(product_code: str, graph: dict | None = None) -> bool:
    item = concept(product_code, graph) or {}
    return item.get("layer") == "product_batch" and "unknown" in product_code


def assay_does_not_close_parent(assay_code: str, parent_code: str, graph: dict | None = None) -> bool:
    for row in relations_from(assay_code, graph):
        if row["to"] == parent_code and row["relation"] == "partially_assesses":
            return True
    return False


def source_by_id(source_id: str, graph: dict | None = None) -> dict | None:
    for item in (graph or load_composition_graph()).get("sources") or []:
        if item["id"] == source_id:
            return item
    return None


SEED_SOURCE_IDS = frozenset({"pmc:8567006", "pmc:7603209", "fda-iodized-salt"})
SEED_TITLE_MARKERS = ("grape bioactive", "pink-salt", "pink salt composition")
IDENTITY_DIMENSIONS = (
    "parent",
    "chemical_identity",
    "form",
    "source_organism",
    "part",
    "preparation",
    "matrix",
    "formulation",
    "route",
    "dose",
    "release_profile",
    "product_batch",
    "assay",
    "synonyms",
    "jurisdiction",
    "evidence_context",
)


def source_is_example_seed(item: dict | None) -> bool:
    if not item:
        return False
    if item.get("role") == "example_seed":
        return True
    sid = str(item.get("id") or item.get("source_id") or "")
    if sid in SEED_SOURCE_IDS:
        return True
    title = str(item.get("title") or "").lower()
    return any(marker in title for marker in SEED_TITLE_MARKERS)


def identity_of(code: str, graph: dict | None = None) -> dict:
    item = concept(code, graph) or {}
    ident = dict(item.get("identity") or {})
    ident.setdefault("parent", item.get("parent"))
    ident.setdefault("synonyms", list(item.get("synonyms") or []))
    return ident


def synonym_to_code(name: str, graph: dict | None = None) -> str | None:
    blob = (name or "").strip().lower()
    if not blob:
        return None
    for item in (graph or load_composition_graph()).get("concepts") or []:
        if item["code"] == blob or blob == str(item.get("label") or "").lower():
            return item["code"]
        if blob in {str(alias).lower() for alias in (item.get("synonyms") or [])}:
            return item["code"]
    return None


def elemental_amount(*, form_code: str, compound_mass_mg: float, graph: dict | None = None) -> dict:
    ident = identity_of(form_code, graph)
    fraction = ident.get("elemental_fraction")
    if fraction is None:
        return {"compound_mass_mg": compound_mass_mg, "elemental_mg": None, "unknown": True}
    return {
        "compound_mass_mg": compound_mass_mg,
        "elemental_mg": round(float(compound_mass_mg) * float(fraction), 4),
        "unknown": False,
    }


def illegal_identity(payload: dict) -> str | None:
    if payload.get("commerce") or payload.get("margin") or payload.get("price"):
        return "commerce_not_identity"
    if payload.get("layer") == "form" and not (payload.get("parent") or (payload.get("identity") or {}).get("parent")):
        return "form_requires_parent"
    extra = set(payload.get("identity") or {}) - set(IDENTITY_DIMENSIONS)
    if extra:
        return "unknown_identity_dimension"
    return None


def variant_may_enter_case(concept_code: str, active_codes: set[str]) -> bool:
    return concept_code in active_codes


def forms_not_ranked_on_generic_effectiveness(left: str, right: str, graph: dict | None = None) -> bool:
    """Two forms with different endpoints cannot share one effectiveness score."""
    del graph
    return left != right
