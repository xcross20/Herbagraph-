"""Stage 5: LLM Reasoning.

Sends a de-identified payload to Claude and asks it to reason *only* from the
evidence snippets retrieved in Stage 4. The response is parsed as strict JSON
and any recommendation citing an ID that wasn't actually retrieved is
discarded — the model cannot free-invent citations that survive into the
final report.
"""

import json

from anthropic import AsyncAnthropic

from app.config import settings
from app.core.privacy import deidentify_payload
from app.schemas.pipeline import EvidenceSnippet, LLMReasoningOutput, LLMRecommendation, NormalizedLabResult, PathwayActivation

_SYSTEM_PROMPT = """You are the clinical reasoning engine for HerbaGraph, a botanical/nutraceutical evidence \
platform. You will be given a patient's abnormal biomarkers, activated biological pathways, and a list of \
evidence snippets (each with an external_id such as "PMID:12345").

Rules:
1. Reason ONLY from the evidence snippets provided. Never invent a citation, study, or finding that is not \
   in the provided evidence list.
2. Every recommendation's cited_study_ids MUST be a subset of the external_id values given in the evidence.
3. Only recommend interventions that appear as `intervention_name` in the evidence snippets.
4. Respond with a single JSON object and nothing else, matching this shape:
{
  "biomarker_pattern_analysis": "string",
  "pathway_summaries": ["string", ...],
  "recommendations": [
    {
      "intervention_name": "string",
      "category": "herb|nutraceutical|lifestyle|peptide|nad_precursor|food|phytochemical|medication|hormone|environmental|behavior",
      "mechanism": "string",
      "evidence_level": "high|moderate|low|preclinical",
      "typical_dose": "string or null",
      "cited_study_ids": ["PMID:12345", ...],
      "rationale": "string or null"
    }
  ],
  "clinician_questions": ["string", ...]
}
"""


class LLMReasoningError(Exception):
    pass


def _build_payload(
    normalized_labs: list[NormalizedLabResult],
    pathway_activations: list[PathwayActivation],
    evidence_snippets: list[EvidenceSnippet],
    health_profile: dict,
) -> dict:
    payload = {
        "abnormal_biomarkers": [
            lab.model_dump(mode="json") for lab in normalized_labs if lab.status.value != "normal"
        ],
        "pathway_activations": [p.model_dump(mode="json") for p in pathway_activations],
        "evidence": [e.model_dump(mode="json") for e in evidence_snippets],
        "health_profile": health_profile,
    }
    return deidentify_payload(payload)


def _valid_external_ids(evidence_snippets: list[EvidenceSnippet]) -> set[str]:
    return {snippet.external_id for snippet in evidence_snippets}


def _sanitize_recommendations(
    raw_recommendations: list[dict], valid_ids: set[str], valid_intervention_names: set[str]
) -> list[LLMRecommendation]:
    sanitized: list[LLMRecommendation] = []
    for raw in raw_recommendations:
        if raw.get("intervention_name") not in valid_intervention_names:
            continue
        cited = [cid for cid in raw.get("cited_study_ids", []) if cid in valid_ids]
        if not cited:
            continue
        raw = {**raw, "cited_study_ids": cited}
        try:
            sanitized.append(LLMRecommendation.model_validate(raw))
        except Exception:
            continue
    return sanitized


def parse_llm_response(raw_text: str, evidence_snippets: list[EvidenceSnippet]) -> LLMReasoningOutput:
    """Parse and safety-filter the raw JSON text returned by Claude."""
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise LLMReasoningError(f"LLM did not return valid JSON: {exc}") from exc

    valid_ids = _valid_external_ids(evidence_snippets)
    valid_names = {snippet.intervention_name for snippet in evidence_snippets}

    recommendations = _sanitize_recommendations(data.get("recommendations", []), valid_ids, valid_names)

    return LLMReasoningOutput(
        biomarker_pattern_analysis=data.get("biomarker_pattern_analysis", ""),
        pathway_summaries=data.get("pathway_summaries", []),
        recommendations=recommendations,
        clinician_questions=data.get("clinician_questions", []),
    )


async def generate_reasoning(
    normalized_labs: list[NormalizedLabResult],
    pathway_activations: list[PathwayActivation],
    evidence_snippets: list[EvidenceSnippet],
    health_profile: dict,
    client: AsyncAnthropic | None = None,
) -> LLMReasoningOutput:
    """Stage 5 entry point: call Claude and return a citation-verified LLMReasoningOutput."""
    if not evidence_snippets:
        return LLMReasoningOutput(
            biomarker_pattern_analysis="No supporting evidence was retrieved for the activated pathways.",
            pathway_summaries=[],
            recommendations=[],
            clinician_questions=[],
        )

    owns_client = client is None
    client = client or AsyncAnthropic(api_key=settings.anthropic_api_key)

    payload = _build_payload(normalized_labs, pathway_activations, evidence_snippets, health_profile)

    try:
        response = await client.messages.create(
            model=settings.llm_model,
            max_tokens=4096,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": json.dumps(payload)}],
        )
    finally:
        if owns_client and hasattr(client, "close"):
            await client.close()

    raw_text = response.content[0].text
    return parse_llm_response(raw_text, evidence_snippets)
