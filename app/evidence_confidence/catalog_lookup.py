"""Resolve intervention metadata (mechanism, compounds, targets) from knowledge-graph catalogs."""

from __future__ import annotations

from functools import lru_cache

from app.knowledge_graph.food_catalog import FOOD_INTERVENTIONS
from app.knowledge_graph.herb_catalog import HERB_INTERVENTIONS
from app.knowledge_graph.lifestyle_methods_catalog import LIFESTYLE_INTERVENTIONS
from app.knowledge_graph.peptide_catalog import PEPTIDE_INTERVENTIONS
from app.knowledge_graph.phytochemical_catalog import PHYTOCHEMICAL_COMPOUNDS
from app.knowledge_graph.supplement_catalog import SUPPLEMENT_INTERVENTIONS
from app.knowledge_graph.tier_a_catalog import TIER_A_INTERVENTIONS, TIER_A_PHYTOCHEMICALS


@lru_cache(maxsize=1)
def _intervention_index() -> dict[str, dict]:
    index: dict[str, dict] = {}
    for catalog in (
        HERB_INTERVENTIONS,
        SUPPLEMENT_INTERVENTIONS,
        PHYTOCHEMICAL_COMPOUNDS,
        PEPTIDE_INTERVENTIONS,
        LIFESTYLE_INTERVENTIONS,
        FOOD_INTERVENTIONS,
        TIER_A_INTERVENTIONS,
        TIER_A_PHYTOCHEMICALS,
    ):
        for entry in catalog:
            index[entry["name"]] = entry
    return index


def lookup_intervention(name: str) -> dict | None:
    return _intervention_index().get(name)


def molecular_targets_for(name: str, pathway_codes: set[str] | None = None) -> list[dict]:
    entry = lookup_intervention(name)
    targets: list[dict] = []
    if entry:
        for compound in entry.get("compounds") or []:
            target = compound.get("primary_target")
            if target:
                targets.append(
                    {
                        "name": target,
                        "compound": compound.get("name"),
                        "provenance_node": f"intervention:{name}",
                    }
                )
    if not targets and pathway_codes:
        for code in sorted(pathway_codes):
            targets.append(
                {
                    "name": code.replace("_", "-"),
                    "compound": None,
                    "provenance_node": f"pathway:{code}",
                }
            )
    return targets