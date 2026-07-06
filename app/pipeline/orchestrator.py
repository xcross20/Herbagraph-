"""Orchestrates the full 7-stage HerbaGraph pipeline end to end."""

import httpx
from anthropic import AsyncAnthropic

from app.pipeline.biomarker_normalizer import normalize_lab_results
from app.pipeline.evidence_retriever import build_intervention_pathway_map, retrieve_evidence
from app.pipeline.lab_parser import parse_lab_file, parse_lab_text
from app.pipeline.llm_reasoner import generate_reasoning
from app.pipeline.pathway_mapper import map_pathways
from app.pipeline.report_generator import generate_report
from app.pipeline.safety_layer import check_safety


async def run_pipeline(
    *,
    file_bytes: bytes | None = None,
    filename: str | None = None,
    raw_text: str | None = None,
    health_profile: dict,
    http_client: httpx.AsyncClient | None = None,
    anthropic_client: AsyncAnthropic | None = None,
) -> dict:
    """Run all 7 pipeline stages and return the final report payload (pre-persistence).

    Exactly one of (file_bytes + filename) or raw_text must be provided.
    """
    if raw_text is not None:
        parsed = parse_lab_text(raw_text)
    elif file_bytes is not None and filename is not None:
        parsed = parse_lab_file(file_bytes, filename)
    else:
        raise ValueError("Either raw_text or (file_bytes and filename) must be provided")

    normalized = normalize_lab_results(parsed)
    pathway_activations = map_pathways(normalized)
    evidence_snippets = await retrieve_evidence(pathway_activations, client=http_client)
    reasoning = await generate_reasoning(
        normalized, pathway_activations, evidence_snippets, health_profile, client=anthropic_client
    )
    safety_report = check_safety(reasoning.recommendations, health_profile)
    intervention_pathways = build_intervention_pathway_map()

    return generate_report(
        normalized,
        pathway_activations,
        evidence_snippets,
        safety_report,
        reasoning.biomarker_pattern_analysis,
        reasoning.clinician_questions,
        intervention_pathways,
    )
