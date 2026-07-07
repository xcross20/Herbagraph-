"""Stage 4: Evidence Retriever.

Builds intervention-specific queries from activated pathways and test-type routing,
concurrently fetches studies from PubMed, ClinicalTrials.gov, and Europe PMC.
"""

import asyncio

import httpx

from app.integrations.clinicaltrials import search_clinicaltrials
from app.integrations.europepmc import search_europepmc
from app.integrations.pubmed import search_pubmed
from app.pipeline.catalog_evidence import build_catalog_evidence_snippets
from app.pipeline.intervention_catalog import (
    build_intervention_pathway_map as _catalog_intervention_pathway_map,
    build_interventions_for_routing,
    build_pathway_intervention_map,
)
from app.pipeline.test_type_router import RecommendationRoutingContext
from app.schemas.pipeline import EvidenceSnippet, NormalizedLabResult, PathwayActivation


def build_intervention_pathway_map(
    routing: RecommendationRoutingContext | None = None,
    pathway_activations: list[PathwayActivation] | None = None,
    normalized_labs: list[NormalizedLabResult] | None = None,
) -> dict[str, list[str]]:
    """Re-export for report pipeline consumers."""
    return _catalog_intervention_pathway_map(routing, pathway_activations, normalized_labs)


def build_query(intervention_name: str, pathway_name: str) -> str:
    """Build a PubMed-style boolean query for an intervention/pathway pair."""
    return f'("{intervention_name}"[Title/Abstract]) AND ("{pathway_name}" OR clinical) AND (trial OR randomized)'


def interventions_for_activations(
    pathway_activations: list[PathwayActivation],
    routing: RecommendationRoutingContext | None = None,
    normalized_labs: list[NormalizedLabResult] | None = None,
) -> dict[str, list[str]]:
    """Map each activated pathway to intervention names for evidence search."""
    if routing and normalized_labs is not None:
        routed = build_interventions_for_routing(routing, pathway_activations, normalized_labs)
        return {k: v for k, v in routed.items() if v}

    pathway_map = build_pathway_intervention_map()
    mapping: dict[str, list[str]] = {}
    for activation in pathway_activations:
        interventions = pathway_map.get(activation.pathway_code, [])
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
    *,
    routing: RecommendationRoutingContext | None = None,
    normalized_labs: list[NormalizedLabResult] | None = None,
) -> list[EvidenceSnippet]:
    """Retrieve, deduplicate, and rank evidence for routed interventions."""
    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=15.0)

    try:
        pathway_to_interventions = interventions_for_activations(
            pathway_activations, routing=routing, normalized_labs=normalized_labs
        )
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
                        intervention_name, pathway_names.get(pathway_code, pathway_code), client, max_results_per_source
                    )
                )

        abnormal_biomarkers = {
            lab.biomarker_name
            for lab in (normalized_labs or [])
            if lab.status.value in ("critical_low", "low", "high", "critical_high")
        }
        pathway_codes = {a.pathway_code for a in pathway_activations}

        catalog_snippets = build_catalog_evidence_snippets(
            seen_interventions,
            abnormal_biomarkers=abnormal_biomarkers,
            pathway_codes=pathway_codes,
            routing=routing,
        )

        if not tasks:
            return _dedupe_and_rank(catalog_snippets)

        results = await asyncio.gather(*tasks)
        live_snippets = [snippet for group in results for snippet in group]
        return _dedupe_and_rank([*catalog_snippets, *live_snippets])
    finally:
        if owns_client:
            await client.aclose()