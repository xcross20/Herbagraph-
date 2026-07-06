"""Stage 5: LLM Reasoning.

Sends a de-identified payload to an OpenAI model and asks it to reason *only*
from the evidence snippets retrieved in Stage 4. The response is parsed as
strict JSON and any recommendation citing an ID that wasn't actually
retrieved is discarded — the model cannot free-invent citations that survive
into the final report.
"""

import json

from openai import AsyncOpenAI

from app.config import settings
from app.core.privacy import deidentify_payload
from app.schemas.pipeline import EvidenceSnippet, LLMReasoningOutput, LLMRecommendation, NormalizedLabResult, PathwayActivation

_SYSTEM_PROMPT = """You are the evidence-reasoning engine for HerbaGraph, a research-support platform \
covering botanicals, phytochemicals, nutraceuticals/supplements, functional foods, and other interventions. \
You are NOT a clinician and this is NOT a diagnosis or prescription. You will be given a patient's abnormal \
biomarkers, activated biological pathways, and a list of evidence snippets (each with an external_id such as \
"PMID:12345").

Evidence rules:
1. Reason ONLY from the evidence snippets provided. Never invent a citation, study, or finding that is not \
   in the provided evidence list.
2. Every recommendation's cited_study_ids MUST be a subset of the external_id values given in the evidence.
3. Only recommend interventions that appear as `intervention_name` in the evidence snippets.

Liability and tone rules -- this is the most important part of your job:
4. Never phrase a recommendation as an instruction to take/do something (e.g. never write "Take 500mg" or \
   "You should start..."). Instead, describe what the cited evidence found, in language like: "Based on the \
   available evidence, X has been studied in populations with elevated Y. This information is intended to \
   support a discussion with a qualified healthcare professional, not to replace one."
5. For `rationale`, answer "why was this surfaced" -- name the specific abnormal biomarker(s) or pathway(s) \
   it addresses.
6. For `limitations`, always state what the cited evidence does NOT show -- e.g. small sample sizes, short \
   study duration, a surrogate endpoint rather than a hard clinical outcome, animal/in-vitro-only evidence, \
   or a population that may not match this patient. Never leave `limitations` null if evidence_level is \
   "low" or "preclinical".
7. `typical_dose`, if given, must describe the dose *used in the cited research* (e.g. "300mg AKBA-\
   standardized extract twice daily, per the cited trial"), not a personal directive to the reader.
8. Do not present any output as a settled medical fact. Every recommendation is provisional and contingent \
   on the cited evidence and the reader's own clinician review.

Respond with a single JSON object and nothing else, matching this shape:
{
  "biomarker_pattern_analysis": "string",
  "pathway_summaries": ["string", ...],
  "recommendations": [
    {
      "intervention_name": "string",
      "category": "food|herb|phytochemical|supplement|exercise|sleep|stress_reduction|medication|peptide|hormone|environmental|behavior",
      "mechanism": "string",
      "evidence_level": "high|moderate|low|preclinical",
      "typical_dose": "string or null",
      "cited_study_ids": ["PMID:12345", ...],
      "rationale": "string or null",
      "limitations": "string or null"
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
    """Parse and safety-filter the raw JSON text returned by the LLM."""
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
    client: AsyncOpenAI | None = None,
) -> LLMReasoningOutput:
    """Stage 5 entry point: call the LLM and return a citation-verified LLMReasoningOutput."""
    if not evidence_snippets:
        abnormal = [lab for lab in normalized_labs if lab.status.value not in ("normal", "optimal")]
        if not abnormal:
            analysis = (
                "Your tracked biomarkers are within reference ranges. No abnormal pathway signals "
                "were detected, so evidence-backed intervention recommendations were not generated. "
                "See the measured biomarker panel below for your parsed lab values."
            )
        elif not pathway_activations:
            analysis = (
                "Abnormal biomarkers were detected but did not map to pathway rules in the MVP panel. "
                "No supporting evidence was retrieved."
            )
        else:
            analysis = "No supporting evidence was retrieved for the activated pathways."
        return LLMReasoningOutput(
            biomarker_pattern_analysis=analysis,
            pathway_summaries=[],
            recommendations=[],
            clinician_questions=[],
        )

    owns_client = client is None
    client = client or AsyncOpenAI(api_key=settings.openai_api_key)

    payload = _build_payload(normalized_labs, pathway_activations, evidence_snippets, health_profile)

    try:
        response = await client.chat.completions.create(
            model=settings.llm_model,
            max_tokens=4096,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload)},
            ],
        )
    finally:
        if owns_client and hasattr(client, "close"):
            await client.close()

    raw_text = response.choices[0].message.content
    return parse_llm_response(raw_text, evidence_snippets)
