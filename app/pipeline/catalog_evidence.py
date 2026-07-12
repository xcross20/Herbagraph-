"""Convert curated Tier A catalog claims into EvidenceSnippet objects.

Live PubMed retrieval often misses etiological interventions (e.g. Mastic Gum for
H. pylori). Stage 4 merges these catalog-backed PMIDs so Stage 5 can recommend
routed interventions without inventing citations.
"""

from __future__ import annotations

from app.knowledge_graph.peptide_catalog import PEPTIDE_EVIDENCE_CLAIMS, PEPTIDE_INTERVENTIONS
from app.knowledge_graph.tier_a_catalog import TIER_A_INTERVENTIONS
from app.knowledge_graph.tier_a_evidence import TIER_A_EVIDENCE_CLAIMS
from app.models.enums import EvidenceLevel, InterventionCategory, RecommendationIntent, RecommendationTree, StudySource, StudyType
from app.pipeline.test_type_router import RecommendationRoutingContext
from app.schemas.pipeline import EvidenceSnippet, LLMReasoningOutput, LLMRecommendation, PathwayActivation

_INTENT_RANK = {
    RecommendationIntent.PRIMARY.value: 0,
    RecommendationIntent.NUTRITIONAL_REPLETION.value: 1,
    RecommendationIntent.COLLATERAL.value: 2,
    RecommendationIntent.CONTEXT_ONLY.value: 3,
}

_EVIDENCE_LEVEL_RANK = {"high": 0, "moderate": 1, "low": 2, "preclinical": 3}

_EVIDENCE_LEVEL_QUALITY = {
    "high": 0.90,
    "moderate": 0.85,
    "low": 0.55,
    "preclinical": 0.20,
}

_EVIDENCE_LEVEL_STUDY_TYPE = {
    "high": StudyType.META_ANALYSIS,
    "moderate": StudyType.RCT,
    "low": StudyType.COHORT,
    "preclinical": StudyType.PRECLINICAL,
}


def _all_catalog_claims() -> list[dict]:
    return [*TIER_A_EVIDENCE_CLAIMS, *PEPTIDE_EVIDENCE_CLAIMS]


def _trees(routing: RecommendationRoutingContext | None) -> list[RecommendationTree]:
    return list(routing.trees) if routing else []


def _matching_claims(
    intervention_name: str,
    abnormal_biomarkers: set[str],
    pathway_codes: set[str],
    trees: list[RecommendationTree],
) -> list[dict]:
    matches: list[dict] = []
    for claim in _all_catalog_claims():
        if claim["intervention_name"] != intervention_name:
            continue

        intent = claim.get("recommendation_intent", RecommendationIntent.PRIMARY.value)
        if intent == RecommendationIntent.CONTEXT_ONLY.value and not (
            RecommendationTree.EXPOSURE in trees or RecommendationTree.PGX_CONTEXT in trees
        ):
            continue

        biomarker = claim.get("biomarker_name")
        pathway = claim.get("pathway_code")

        if biomarker and biomarker in abnormal_biomarkers:
            matches.append(claim)
        elif pathway and pathway in pathway_codes:
            matches.append(claim)

    return matches


def _rank_claim(claim: dict) -> tuple[int, int]:
    intent = claim.get("recommendation_intent", RecommendationIntent.COLLATERAL.value)
    level = claim.get("evidence_level", "low")
    return (_INTENT_RANK.get(intent, 9), _EVIDENCE_LEVEL_RANK.get(level, 9))


def _claim_to_snippet(claim: dict) -> EvidenceSnippet:
    pmid = str(claim["pmid"])
    level = claim.get("evidence_level", "low")
    summary = claim.get("summary", "")
    intervention = claim["intervention_name"]
    title = f"{intervention}: {summary}" if summary else intervention

    return EvidenceSnippet(
        source=StudySource.PUBMED,
        external_id=f"PMID:{pmid}",
        title=title,
        year=None,
        study_type=_EVIDENCE_LEVEL_STUDY_TYPE.get(level, StudyType.COHORT),
        quality_score=_EVIDENCE_LEVEL_QUALITY.get(level, 0.55),
        url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        abstract_snippet=summary or None,
        intervention_name=intervention,
    )


def build_catalog_evidence_snippets(
    intervention_names: set[str] | list[str],
    *,
    abnormal_biomarkers: set[str] | None = None,
    pathway_codes: set[str] | None = None,
    routing: RecommendationRoutingContext | None = None,
) -> list[EvidenceSnippet]:
    """Build one catalog-backed snippet per routed intervention (best matching claim)."""
    names = set(intervention_names)
    if not names:
        return []

    biomarkers = abnormal_biomarkers or set()
    pathways = pathway_codes or set()
    trees = _trees(routing)

    snippets: list[EvidenceSnippet] = []
    seen_pmids: set[str] = set()

    for intervention_name in sorted(names):
        claims = _matching_claims(intervention_name, biomarkers, pathways, trees)
        if not claims:
            continue

        best = min(claims, key=_rank_claim)
        pmid = str(best["pmid"])
        dedupe_key = f"{intervention_name}:{pmid}"
        if dedupe_key in seen_pmids:
            continue
        seen_pmids.add(dedupe_key)
        snippets.append(_claim_to_snippet(best))

    return snippets


_PRIMARY_TREE_GUARDS = frozenset({
    RecommendationTree.ETIOLOGICAL,
    RecommendationTree.CELIAC,
    RecommendationTree.CULTURE,
    RecommendationTree.ALLERGY,
    RecommendationTree.NUTRITIONAL_REPLETION,
})

_INTERVENTION_CATEGORY: dict[str, InterventionCategory] = {
    entry["name"]: InterventionCategory(entry["category"])
    for entry in [*TIER_A_INTERVENTIONS, *PEPTIDE_INTERVENTIONS]
}


def _category_for(intervention_name: str) -> InterventionCategory:
    return _INTERVENTION_CATEGORY.get(intervention_name, InterventionCategory.SUPPLEMENT)


def _evidence_level_for_snippet(snippet: EvidenceSnippet) -> EvidenceLevel:
    if snippet.quality_score >= 0.85:
        return EvidenceLevel.HIGH
    if snippet.quality_score >= 0.65:
        return EvidenceLevel.MODERATE
    if snippet.quality_score >= 0.35:
        return EvidenceLevel.LOW
    return EvidenceLevel.PRECLINICAL


def build_catalog_reasoning_output(
    evidence_snippets: list[EvidenceSnippet],
    *,
    abnormal_biomarkers: set[str],
    pathway_activations: list[PathwayActivation],
    routing: RecommendationRoutingContext | None = None,
) -> LLMReasoningOutput:
    """Deterministic Stage 5 output from curated catalog evidence (no LLM call)."""
    if not evidence_snippets:
        if not abnormal_biomarkers:
            analysis = (
                "Your tracked biomarkers are within reference ranges. No abnormal pathway signals "
                "were detected, so evidence-backed intervention recommendations were not generated."
            )
        elif not pathway_activations:
            analysis = (
                "Abnormal biomarkers were detected but did not map to pathway rules. "
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

    abnormal_list = ", ".join(sorted(abnormal_biomarkers))
    pathway_summaries = [
        f"{activation.pathway_name} shows an evidence-weighted signal "
        f"({activation.direction.value}) from {', '.join(activation.contributing_biomarkers)}."
        for activation in pathway_activations
        if activation.contributing_biomarkers
    ]

    recommendations: list[LLMRecommendation] = []
    seen_interventions: set[str] = set()
    snippets_by_intervention: dict[str, list[EvidenceSnippet]] = {}
    for snippet in evidence_snippets:
        snippets_by_intervention.setdefault(snippet.intervention_name, []).append(snippet)

    for intervention_name in sorted(snippets_by_intervention):
        if intervention_name in seen_interventions:
            continue
        seen_interventions.add(intervention_name)
        group = snippets_by_intervention[intervention_name]
        best = max(group, key=lambda s: s.quality_score)
        cited = [s.external_id for s in group if s.external_id][:3]
        if not cited:
            continue
        recommendations.append(
            LLMRecommendation(
                intervention_name=intervention_name,
                category=_category_for(intervention_name),
                mechanism=best.abstract_snippet or best.title,
                evidence_level=_evidence_level_for_snippet(best),
                typical_dose=None,
                cited_study_ids=cited,
                rationale=(
                    f"Surfaced from curated catalog evidence because {abnormal_list} "
                    f"were abnormal and routed interventions include {intervention_name}."
                ),
                limitations=(
                    "This summary is drawn from curated catalog evidence; study populations, "
                    "dosing, and clinical endpoints may differ from this patient's context."
                ),
            )
        )

    output = LLMReasoningOutput(
        biomarker_pattern_analysis=(
            f"Abnormal biomarkers ({abnormal_list}) activated nutritional and hematologic "
            "pathway signals. Recommendations below are drawn from curated catalog evidence "
            "for clinician discussion, not as directives."
        ),
        pathway_summaries=pathway_summaries,
        recommendations=recommendations,
        clinician_questions=[
            "Have B12, folate, and iron studies been checked to explain macrocytic indices?"
        ]
        if {"MCV", "MCH", "RDW"} & abnormal_biomarkers
        else [],
    )
    return ensure_primary_recommendations(
        output,
        evidence_snippets,
        abnormal_biomarkers=abnormal_biomarkers,
        routing=routing,
    )


def stabilize_reasoning_output(
    llm_output: LLMReasoningOutput,
    evidence_snippets: list[EvidenceSnippet],
    *,
    abnormal_biomarkers: set[str],
    pathway_activations: list[PathwayActivation],
    routing: RecommendationRoutingContext | None = None,
) -> LLMReasoningOutput:
    """Merge LLM prose with a deterministic catalog recommendation set.

    Stages 1–4 and 6–7 are already provider-independent; this keeps Stage 5 from
    surfacing different interventions depending on which model is configured.
    """
    catalog = build_catalog_reasoning_output(
        evidence_snippets,
        abnormal_biomarkers=abnormal_biomarkers,
        pathway_activations=pathway_activations,
        routing=routing,
    )
    llm_by_name = {rec.intervention_name: rec for rec in llm_output.recommendations}

    merged_recommendations: list[LLMRecommendation] = []
    for catalog_rec in catalog.recommendations:
        llm_rec = llm_by_name.get(catalog_rec.intervention_name)
        merged_recommendations.append(llm_rec if llm_rec is not None else catalog_rec)

    analysis = (llm_output.biomarker_pattern_analysis or "").strip()
    if not analysis:
        analysis = catalog.biomarker_pattern_analysis

    pathway_summaries = llm_output.pathway_summaries or catalog.pathway_summaries
    clinician_questions = llm_output.clinician_questions or catalog.clinician_questions

    return LLMReasoningOutput(
        biomarker_pattern_analysis=analysis,
        pathway_summaries=pathway_summaries,
        recommendations=merged_recommendations,
        clinician_questions=clinician_questions,
    )


def ensure_primary_recommendations(
    output: LLMReasoningOutput,
    evidence_snippets: list[EvidenceSnippet],
    *,
    abnormal_biomarkers: set[str],
    routing: RecommendationRoutingContext | None = None,
) -> LLMReasoningOutput:
    """Inject biomarker-direct primary catalog recommendations the LLM may have skipped."""
    if not routing or routing.primary_tree not in _PRIMARY_TREE_GUARDS:
        return output

    existing = {rec.intervention_name for rec in output.recommendations}
    snippet_ids = {snippet.external_id for snippet in evidence_snippets}
    snippets_by_intervention: dict[str, list[EvidenceSnippet]] = {}
    for snippet in evidence_snippets:
        snippets_by_intervention.setdefault(snippet.intervention_name, []).append(snippet)

    injected: list[LLMRecommendation] = []
    for claim in _all_catalog_claims():
        if claim.get("recommendation_intent") != RecommendationIntent.PRIMARY.value:
            continue
        biomarker = claim.get("biomarker_name")
        if not biomarker or biomarker not in abnormal_biomarkers:
            continue

        name = claim["intervention_name"]
        if name in existing or name in {rec.intervention_name for rec in injected}:
            continue

        intervention_snippets = snippets_by_intervention.get(name, [])
        cited = [
            snippet.external_id
            for snippet in intervention_snippets
            if snippet.external_id in snippet_ids
        ]
        if not cited:
            continue

        level = claim.get("evidence_level", "low")
        summary = claim.get("summary", "")
        injected.append(
            LLMRecommendation(
                intervention_name=name,
                category=_category_for(name),
                mechanism=summary or f"Studied in relation to {biomarker}.",
                evidence_level=EvidenceLevel(level),
                typical_dose=None,
                cited_study_ids=cited[:3],
                rationale=(
                    f"Surfaced because {biomarker} was abnormal and curated evidence links "
                    f"{name} to this etiological pathway."
                ),
                limitations=(
                    "This summary is drawn from curated catalog evidence; study populations, "
                    "dosing, and clinical endpoints may differ from this patient's context."
                ),
            )
        )

    if not injected:
        return output

    return output.model_copy(update={"recommendations": [*injected, *output.recommendations]})