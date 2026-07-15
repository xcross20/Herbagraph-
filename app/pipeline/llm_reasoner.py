"""Stage 5: LLM Reasoning.

Sends a de-identified payload to an OpenAI model and asks it to reason *only*
from the evidence snippets retrieved in Stage 4. The response is parsed as
strict JSON and any recommendation citing an ID that wasn't actually
retrieved is discarded — the model cannot free-invent citations that survive
into the final report.
"""

import json
import os

from app.config import get_settings
from app.pipeline.llm_client import (
    APIConnectionError,
    APITimeoutError,
    AsyncOpenAI,
    async_chat_json_with_fallback,
    create_async_client,
    llm_api_key,
)
from app.core.privacy import deidentify_payload
from app.pipeline.catalog_evidence import (
    build_catalog_reasoning_output,
    ensure_primary_recommendations,
    stabilize_reasoning_output,
)
from app.pipeline.test_type_router import RecommendationRoutingContext
from app.schemas.pipeline import EvidenceSnippet, LLMReasoningOutput, LLMRecommendation, NormalizedLabResult, PathwayActivation

_SYSTEM_PROMPT = """You are the evidence-reasoning engine for HerbaGraph, a research-support platform \
covering botanicals, phytochemicals, nutraceuticals/supplements, functional foods, clinically evidenced peptides, and other interventions. \
You are NOT a clinician and this is NOT a diagnosis or prescription. You will be given a patient's abnormal \
biomarkers, activated biological pathways, and a list of evidence snippets (each with an external_id such as \
"PMID:12345").

Evidence rules:
1. Reason ONLY from the evidence snippets provided. Never invent a citation, study, or finding that is not \
   in the provided evidence list.
2. Every recommendation's cited_study_ids MUST be a subset of the external_id values given in the evidence.
3. Only recommend interventions that appear as `intervention_name` in the evidence snippets.
4. When both a herb and its corresponding phytochemical appear in the evidence (e.g. Curcumin vs turmeric compounds), \
   prefer the **phytochemical** category so the food-compound layer can attach whole-food sources.
5. For activated inflammatory or metabolic pathways, include at least one **phytochemical** or **food** recommendation \
   when the evidence list contains one — these connect to whole-food sources in the report.
6. When `routing.primary_tree` is etiological, celiac, culture, allergy, or nutritional_repletion, prioritize \
   biomarker-direct **primary** interventions for the detected condition (e.g. Mastic Gum for active H. pylori, \
   DGL Licorice for gastric mucosal support) over generic inflammatory pathway supplements.

Liability and tone rules -- this is the most important part of your job:
7. Never phrase a recommendation as an instruction to take/do something (e.g. never write "Take 500mg" or \
   "You should start..."). Instead, describe what the cited evidence found, in language like: "Based on the \
   available evidence, X has been studied in populations with elevated Y. This information is intended to \
   support a discussion with a qualified healthcare professional, not to replace one."
8. For `rationale`, answer "why was this surfaced" -- name the specific abnormal biomarker(s) or pathway(s) \
   it addresses.
9. For `limitations`, always state what the cited evidence does NOT show -- e.g. small sample sizes, short \
   study duration, a surrogate endpoint rather than a hard clinical outcome, animal/in-vitro-only evidence, \
   or a population that may not match this patient. Never leave `limitations` null if evidence_level is \
   "low" or "preclinical".
10. `typical_dose`, if given, must describe the dose *used in the cited research* (e.g. "300mg AKBA-\
   standardized extract twice daily, per the cited trial"), not a personal directive to the reader.
11. Do not present any output as a settled medical fact. Every recommendation is provisional and contingent \
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


def _use_catalog_only_reasoning() -> bool:
    """CI and local tests use catalog-backed reasoning when no production API key is set."""
    flag = os.environ.get("HERBAGRAPH_CATALOG_ONLY_REASONING", "").lower()
    if flag in ("1", "true", "yes"):
        return True
    key = llm_api_key()
    if not key:
        return True
    return key.startswith("test-")


def _catalog_fallback_for_llm_failure(exc: Exception) -> bool:
    """Use curated catalog reasoning when OpenAI is unreachable."""
    if _use_catalog_only_reasoning():
        return True
    return isinstance(exc, (APIConnectionError, APITimeoutError, ConnectionError))


def _catalog_reasoning_with_fallback_note(
    evidence_snippets: list[EvidenceSnippet],
    *,
    abnormal_biomarkers: set[str],
    pathway_activations: list[PathwayActivation],
    routing: RecommendationRoutingContext | None,
    exc: Exception | None = None,
) -> LLMReasoningOutput:
    output = build_catalog_reasoning_output(
        evidence_snippets,
        abnormal_biomarkers=abnormal_biomarkers,
        pathway_activations=pathway_activations,
        routing=routing,
    )
    prefix = (
        "LLM reasoning was unavailable (provider connection failed). "
        "This report uses curated catalog evidence instead. "
    )
    if exc is not None:
        prefix += f"Technical detail: {exc}. "
    return output.model_copy(
        update={
            "biomarker_pattern_analysis": prefix + output.biomarker_pattern_analysis,
        }
    )


def _build_payload(
    normalized_labs: list[NormalizedLabResult],
    pathway_activations: list[PathwayActivation],
    evidence_snippets: list[EvidenceSnippet],
    health_profile: dict,
    routing: RecommendationRoutingContext | None = None,
) -> dict:
    payload = {
        "abnormal_biomarkers": [
            lab.model_dump(mode="json") for lab in normalized_labs if lab.status.value != "normal"
        ],
        "pathway_activations": [p.model_dump(mode="json") for p in pathway_activations],
        "evidence": [e.model_dump(mode="json") for e in evidence_snippets],
        "health_profile": health_profile,
    }
    if routing is not None:
        payload["routing"] = {
            "primary_tree": routing.primary_tree.value if routing.primary_tree else None,
            "trees": [tree.value for tree in routing.trees],
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
    *,
    routing: RecommendationRoutingContext | None = None,
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

    abnormal_biomarkers = {
        lab.biomarker_name
        for lab in normalized_labs
        if lab.status.value in ("critical_low", "low", "high", "critical_high")
    }

    if client is None and _use_catalog_only_reasoning():
        return build_catalog_reasoning_output(
            evidence_snippets,
            abnormal_biomarkers=abnormal_biomarkers,
            pathway_activations=pathway_activations,
            routing=routing,
        )

    owns_client = client is None
    client = client or create_async_client()

    payload = _build_payload(
        normalized_labs, pathway_activations, evidence_snippets, health_profile, routing=routing
    )

    fallback_provider: str | None = None
    try:
        try:
            raw_text, fallback_provider = await async_chat_json_with_fallback(
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps(payload)},
                ],
                client=client,
            )
        except Exception as exc:
            if _catalog_fallback_for_llm_failure(exc):
                return _catalog_reasoning_with_fallback_note(
                    evidence_snippets,
                    abnormal_biomarkers=abnormal_biomarkers,
                    pathway_activations=pathway_activations,
                    routing=routing,
                    exc=exc,
                )
            raise LLMReasoningError(str(exc)) from exc
    finally:
        if owns_client and hasattr(client, "close"):
            await client.close()
    output = parse_llm_response(raw_text, evidence_snippets)
    if fallback_provider:
        note = (
            f"Primary LLM provider hit a token or rate limit; reasoning completed via {fallback_provider}. "
        )
        output = output.model_copy(
            update={
                "biomarker_pattern_analysis": note + output.biomarker_pattern_analysis,
            }
        )
    if get_settings().llm_stabilize_reasoning:
        output = stabilize_reasoning_output(
            output,
            evidence_snippets,
            abnormal_biomarkers=abnormal_biomarkers,
            pathway_activations=pathway_activations,
            routing=routing,
        )
    return ensure_primary_recommendations(
        output,
        evidence_snippets,
        abnormal_biomarkers=abnormal_biomarkers,
        routing=routing,
    )
