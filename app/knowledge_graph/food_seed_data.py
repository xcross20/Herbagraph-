"""Food -> Compound knowledge graph layer (200 foods, 200 phytochemicals, 200+ links)."""

from app.knowledge_graph.food_catalog import FOOD_INTERVENTIONS
from app.knowledge_graph.food_compound_links import FOOD_COMPOUND_SOURCES
from app.knowledge_graph.food_evidence_catalog import FOOD_COMPOUND_EVIDENCE_CLAIMS
from app.knowledge_graph.food_lookups import COMPOUND_TO_FOOD_SOURCES, FOOD_TO_COMPOUNDS
from app.knowledge_graph.phytochemical_catalog import PHYTOCHEMICAL_COMPOUNDS
from app.knowledge_graph.seed_data import EVIDENCE_CLAIMS

_PHYTO_NAMES = {p["name"] for p in PHYTOCHEMICAL_COMPOUNDS}

FOOD_COMPOUND_EVIDENCE_CLAIMS: list[dict] = [
    *FOOD_COMPOUND_EVIDENCE_CLAIMS,
    *[c for c in EVIDENCE_CLAIMS if c["intervention_name"] in _PHYTO_NAMES],
]

__all__ = [
    "PHYTOCHEMICAL_COMPOUNDS",
    "FOOD_INTERVENTIONS",
    "FOOD_COMPOUND_SOURCES",
    "FOOD_COMPOUND_EVIDENCE_CLAIMS",
    "COMPOUND_TO_FOOD_SOURCES",
    "FOOD_TO_COMPOUNDS",
]