"""Stage 4: Evidence Retriever.

Builds intervention-specific queries from activated pathways, concurrently
fetches studies from PubMed, ClinicalTrials.gov, and Europe PMC, deduplicates
by external ID, and ranks by study quality.
"""

import asyncio

import httpx

from app.integrations.clinicaltrials import search_clinicaltrials
from app.integrations.europepmc import search_europepmc
from app.integrations.pubmed import search_pubmed
from app.schemas.pipeline import EvidenceSnippet, PathwayActivation

# pathway_code -> intervention names pulled into evidence retrieval for that pathway.
# Mixes core herbs/nutraceuticals/lifestyle (seed_data.INTERVENTIONS) with
# food-layer phytochemical compounds (food_seed_data.PHYTOCHEMICAL_COMPOUNDS).
_PATHWAY_INTERVENTIONS: dict[str, list[str]] = {
    "NF_KB": ["Boswellia serrata", "Curcumin", "Omega-3", "Sulforaphane", "Allicin", "Quercetin"],
    "IL6_JAK_STAT3": ["Curcumin", "Omega-3"],
    "AMPK": ["Berberine", "Alpha Lipoic Acid", "Intermittent Fasting", "HIIT", "EGCG"],
    "INSULIN_PI3K_AKT": ["Berberine", "Magnesium", "Alpha Lipoic Acid", "Intermittent Fasting", "HIIT"],
    "NRF2": ["Milk Thistle", "Sulforaphane", "Anthocyanins", "Ellagic Acid", "Lycopene", "Beta-Carotene"],
    "MTOR_AUTOPHAGY": ["Intermittent Fasting"],
    "HPA_AXIS": ["Ashwagandha"],
    "THYROID_HPT": [],
    "HEPATIC_LIPID": ["Berberine", "Omega-3", "Milk Thistle", "Allicin", "Lycopene"],
    "ONE_CARBON_METHYLATION": [],
    "GLP1_INCRETINS": [],
    "MITOCHONDRIAL_NAD": ["NAD+ Precursors (NR/NMN)", "CoQ10"],
    "IRON_HEPCIDIN": [],
    "PURINE_URIC_ACID": ["Quercetin"],
    "VITAMIN_D_RECEPTOR": ["Vitamin D"],
    "RENAL_FILTRATION": [],
}


def build_query(intervention_name: str, pathway_name: str) -> str:
    """Build a PubMed-style boolean query for an intervention/pathway pair."""
    return f'("{intervention_name}"[Title/Abstract]) AND ("{pathway_name}" OR clinical) AND (trial OR randomized)'


def build_intervention_pathway_map() -> dict[str, list[str]]:
    """Invert _PATHWAY_INTERVENTIONS into intervention_name -> [pathway_code, ...]."""
    mapping: dict[str, list[str]] = {}
    for pathway_code, intervention_names in _PATHWAY_INTERVENTIONS.items():
        for name in intervention_names:
            mapping.setdefault(name, []).append(pathway_code)
    return mapping


def interventions_for_activations(pathway_activations: list[PathwayActivation]) -> dict[str, list[str]]:
    """Map each activated pathway to the intervention names that should be evidence-searched for it."""
    mapping: dict[str, list[str]] = {}
    for activation in pathway_activations:
        interventions = _PATHWAY_INTERVENTIONS.get(activation.pathway_code, [])
        if interventions:
            mapping[activation.pathway_code] = interventions
    return mapping


def _dedupe_and_rank(snippets: list[EvidenceSnippet]) -> list[EvidenceSnippet]:
    seen: dict[str, EvidenceSnippet] = {}
    for snippet in snippets:
        key = f"{snippet.intervention_name}:{snippet.external_id}"
        existing = seen.get(key)
        if existing is None or snippet.quality_score > existing.quality_score:
            seen[key] = snippet
    return sorted(seen.values(), key=lambda s: s.quality_score, reverse=True)


async def _fetch_for_intervention(
    intervention_name: str, pathway_name: str, client: httpx.AsyncClient, max_results_per_source: int
) -> list[EvidenceSnippet]:
    query = build_query(intervention_name, pathway_name)
    results = await asyncio.gather(
        search_pubmed(query, client, intervention_name, max_results_per_source),
        search_clinicaltrials(query, client, intervention_name, max_results_per_source),
        search_europepmc(query, client, intervention_name, max_results_per_source),
        return_exceptions=True,
    )
    snippets: list[EvidenceSnippet] = []
    for result in results:
        if isinstance(result, Exception):
            continue
        snippets.extend(result)
    return snippets


async def retrieve_evidence(
    pathway_activations: list[PathwayActivation],
    client: httpx.AsyncClient | None = None,
    max_results_per_source: int = 5,
) -> list[EvidenceSnippet]:
    """Retrieve, deduplicate, and rank evidence for every intervention implicated by activated pathways."""
    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=15.0)

    try:
        pathway_to_interventions = interventions_for_activations(pathway_activations)
        pathway_names = {a.pathway_code: a.pathway_name for a in pathway_activations}

        seen_interventions: set[str] = set()
        tasks = []
        for pathway_code, intervention_names in pathway_to_interventions.items():
            for intervention_name in intervention_names:
                if intervention_name in seen_interventions:
                    continue
                seen_interventions.add(intervention_name)
                tasks.append(
                    _fetch_for_intervention(
                        intervention_name, pathway_names[pathway_code], client, max_results_per_source
                    )
                )

        if not tasks:
            return []

        results = await asyncio.gather(*tasks)
        all_snippets = [snippet for group in results for snippet in group]
        return _dedupe_and_rank(all_snippets)
    finally:
        if owns_client:
            await client.aclose()
