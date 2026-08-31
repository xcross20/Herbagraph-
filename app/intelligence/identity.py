"""Identity Engine adapter.

Wraps: app.discovery.composition
Contract: docs/personal-evidence/REASONING_CORE_ARCHITECTURE.md §3.1

Identity invariants enforced here:
  - magnesium != magnesium glycinate
  - oxide evidence does NOT automatically transfer to glycinate
  - unknown magnesium product stays unknown
  - compound mass and elemental magnesium stay distinct
  - missing elemental fraction is unknown, not zero
  - B12 assays are measurements with their own coverage semantics
  - parent evidence cannot silently become child-form evidence
  - commerce can never alter scientific identity
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

# ── Delegation ──────────────────────────────────────────────────────────────

from app.discovery.composition import (  # noqa: E402
    INHERITANCE_FORBIDDEN,
    IDENTITY_DIMENSIONS,
    KNOWN_LAYERS,
    claim_transfers as _claim_transfers,
    concept as _concept,
    elemental_amount as _elemental_amount,
    forms_not_ranked_on_generic_effectiveness as _forms_not_ranked,
    identity_of as _identity_of,
    load_composition_graph as _load_graph,
    overlay_uses_existing_layers as _overlay_uses_existing,
    relations_from as _relations_from,
    source_by_id as _source_by_id,
    synonym_to_code as _synonym_to_code,
)

# ── Typed result ────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ClaimTransferResult:
    """Outcome of an evidence-transfer assessment between two concept codes."""

    allowed: bool
    reasons: tuple[str, ...]
    blocked_by: tuple[str, ...]
    provenance: str


# ── Public API ──────────────────────────────────────────────────────────────


def load_composition_graph() -> dict:
    """Load the versioned composition graph. Cached by LRU in the delegate."""
    return _load_graph()


def overlay_uses_existing_layers(overlay: dict) -> bool:
    """True when the overlay only uses existing identity layers (no schema change)."""
    return _overlay_uses_existing(overlay)


def claim_transfers(source_code: str, target_code: str, relation: str) -> bool:
    """
    Returns False when:
      - relation is in INHERITANCE_FORBIDDEN
      - source is product_batch and target is not product_batch
      - source is preparation and target is phenotype or concept
      - a "does_not_address" relation exists from source to target
    """
    return _claim_transfers(source_code, target_code, relation)


def assess_claim_transfer(source_code: str, target_code: str, relation: str) -> ClaimTransferResult:
    """Full transfer assessment with typed reasons and provenance.

    DENY-BY-DEFAULT: allowed=True only when an affirmative entitlement exists.
    The absence of a blocking rule does NOT establish transfer entitlement.

    Positive entitlement cases (allowed=True):
      - source_code == target_code: evidence trivially transfers to itself

    All other cases are denied by default. To establish entitlement, a governed
    'allowed' relation must exist in the composition graph, or an explicit
    inheritance transfer must be authorized by the identity catalog.
    """
    graph = load_composition_graph()
    src = _concept(source_code, graph) or {}
    dst = _concept(target_code, graph) or {}
    reasons: list[str] = []
    blocked_by: list[str] = []

    # Explicit entitlement: same concept trivially transfers to itself
    if source_code == target_code:
        return ClaimTransferResult(
            allowed=True,
            reasons=("Same concept — evidence trivially transfers.",),
            blocked_by=(),
            provenance=src.get("parent") or src.get("layer") or "unknown",
        )

    # Structural inheritance barriers
    if relation in INHERITANCE_FORBIDDEN:
        reasons.append(f"'{relation}' evidence does not transfer across parent/child or batch/category edges.")
        blocked_by.append("INHERITANCE_FORBIDDEN")

    if src.get("layer") == "product_batch" and dst.get("layer") != "product_batch":
        reasons.append("Batch-level evidence does not transfer to every category-level product.")
        blocked_by.append("batch_to_non_batch")

    if src.get("layer") == "preparation" and dst.get("layer") in {"phenotype", "concept"}:
        reasons.append("Preparation evidence does not automatically transfer to the parent concept.")
        blocked_by.append("preparation_to_concept")

    for row in _relations_from(source_code, graph):
        if row["to"] == target_code and row["relation"] == "does_not_address":
            reasons.append(row.get("limitation") or "A 'does_not_address' relation exists between source and target.")
            blocked_by.append("does_not_address")

    provenance = src.get("parent") or src.get("layer") or "unknown"

    # DENY BY DEFAULT: absence of a blocking rule does NOT grant entitlement
    # Only explicit 'allowed' relations (not yet in graph) would enable transfer
    return ClaimTransferResult(
        allowed=False,
        reasons=tuple(reasons) if reasons else ("No affirmative transfer entitlement found.",),
        blocked_by=tuple(blocked_by) if blocked_by else ("TRANSFER_ENTITLEMENT_UNESTABLISHED",),
        provenance=provenance,
    )


def elemental_amount(form_code: str, compound_mass_mg: float) -> dict:
    """
    Calculate elemental amount from compound mass.

    Returns {"compound_mass_mg": float, "elemental_mg": float | None, "unknown": bool}
    - unknown=True when elemental_fraction is not known for this form
    - unknown is never inferred or zero-filled
    """
    return _elemental_amount(form_code=form_code, compound_mass_mg=compound_mass_mg, graph=None)


def forms_not_rankable_on_generic_effectiveness(left: str, right: str) -> bool:
    """True when two forms have different endpoints and cannot share a generic effectiveness score."""
    return _forms_not_ranked(left, right, None)


def identity_of(code: str) -> dict:
    """Return the identity dimensions for a concept code, or empty dict."""
    return _identity_of(code, None)


def layer_for(code: str) -> str | None:
    """Return the identity layer for a concept code."""
    item = _concept(code, None)
    return item.get("layer") if item else None


def parent_of(code: str) -> str | None:
    """Return the parent concept code, or None."""
    item = _concept(code, None)
    return item.get("parent") if item else None


def synonym_to_code(name: str) -> str | None:
    """Resolve a human-readable name to a canonical concept code."""
    return _synonym_to_code(name, None)


def available_forms(parent_code: str) -> list[dict]:
    """Return all form-layer concepts that have the given parent code."""
    graph = load_composition_graph()
    return [
        {"code": c["code"], "label": c.get("label", c["code"])}
        for c in graph.get("concepts", [])
        if c.get("layer") == "form" and c.get("parent") == parent_code
    ]


def form_code_for(form_name: str) -> str | None:
    """Return the canonical code for a form name or alias."""
    return synonym_to_code(form_name)


def source_for(source_id: str) -> dict | None:
    """Return the provenance source record for a source ID."""
    return _source_by_id(source_id, None)


# ── Constants (re-exported) ─────────────────────────────────────────────────


known_layers: frozenset[str] = KNOWN_LAYERS
"""The 10 canonical identity layers: concept, subtype, phenotype, part, form,
preparation, product_batch, exposure, assay, measured_composition, claim."""

identity_dimensions: tuple[str, ...] = IDENTITY_DIMENSIONS
"""The 16 identity dimensions: parent, chemical_identity, form, source_organism,
part, preparation, matrix, formulation, route, dose, release_profile,
product_batch, assay, synonyms, jurisdiction, evidence_context."""
