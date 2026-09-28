"""Metabolic names resolve through the composition graph.

Goldenseal is not berberine. Cassia is not Ceylon. Unspecified cinnamon
stays an unknown product. Monacolin measured in one batch is not every
red yeast rice product.
"""

from __future__ import annotations

from app.discovery.composition import (
    claim_transfers,
    concept,
    load_metabolic_graph,
    relations_from,
    synonym_to_code,
)


def resolve_metabolic_code(name: str) -> str | None:
    return synonym_to_code(name, load_metabolic_graph())


def clinical_flags(code: str) -> dict:
    item = concept(code, load_metabolic_graph()) or {}
    return dict(item.get("clinical") or {})


def explicitly_does_not_address(source_code: str, target_code: str) -> bool:
    graph = load_metabolic_graph()
    return any(
        row.get("to") == target_code and row.get("relation") == "does_not_address"
        for row in relations_from(source_code, graph)
    )


def outcome_evidence_transfers(source_code: str, target_code: str) -> bool:
    return claim_transfers(
        source_code,
        target_code,
        "supports_outcome_in_population",
        load_metabolic_graph(),
    )
