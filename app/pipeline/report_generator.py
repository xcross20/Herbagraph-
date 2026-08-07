"""Stage 7: Report Generator.

Applies the composite confidence scoring formula, ranks surviving
recommendations, and assembles the final structured report.
"""

from app.core.disclaimers import REPORT_DISCLAIMER
from app.evidence_confidence.citations import resolve_study_url
from app.evidence_confidence.engine import build_explainability_bundle
from app.pipeline.food_source_resolver import attach_food_sources
from app.pipeline.intervention_catalog import intent_for_intervention
from app.pipeline.intervention_narrative import build_intervention_narrative
from app.pipeline.test_type_router import RecommendationRoutingContext
from app.models.enums import EVIDENCE_TIER_LABELS, EvidenceLevel, EvidenceTier, SafetyRiskLevel, StudyType
from app.pipeline.biological_systems import compute_biological_systems
from app.pipeline.condition_lanes import build_condition_aligned
from app.pipeline.report_insights import build_report_insights
from app.pipeline.report_biological_hierarchy import biology_first_network_score, build_biological_hierarchy
from app.pipeline.report_clinical_priorities import build_dual_clinical_rankings
from app.pipeline.report_clinical_summary import build_clinical_summary_hero
from app.pipeline.report_intent import classify_display_intent
from app.pipeline.report_tiering import build_recommendation_tiers
from app.safety_engine.scoring import adjusted_confidence
from app.schemas.pipeline import EvidenceSnippet, NormalizedLabResult, PathwayActivation, SafetyReport, ScoredRecommendation

DISCLAIMER = REPORT_DISCLAIMER

_BIOMARKER_STATUS_PHRASES: dict[str, str] = {
    "critical_low": "critically low",
    "low": "low",
    "high": "high",
    "critical_high": "critically high",
}

MODEL_VERSION = "1.0.0"

_EVIDENCE_STRENGTH: dict[EvidenceLevel, float] = {
    EvidenceLevel.HIGH: 0.95,
    EvidenceLevel.MODERATE: 0.65,
    EvidenceLevel.LOW: 0.35,
    EvidenceLevel.PRECLINICAL: 0.20,
}

_SAFETY_RISK_SCORE: dict[SafetyRiskLevel, float] = {
    SafetyRiskLevel.LOW: 0.00,
    SafetyRiskLevel.MODERATE: 0.40,
    SafetyRiskLevel.HIGH: 0.75,
    SafetyRiskLevel.CONTRAINDICATED: 1.00,
}


def _study_quality(recommendation: ScoredRecommendation, evidence_by_id: dict[str, EvidenceSnippet]) -> float:
    scores = [
        evidence_by_id[cid].quality_score for cid in recommendation.cited_study_ids if cid in evidence_by_id
    ]
    return sum(scores) / len(scores) if scores else 0.0


def _pathway_relevance(
    recommendation: ScoredRecommendation,
    pathway_activations: list[PathwayActivation],
    intervention_pathways: dict[str, list[str]],
) -> float:
    codes = intervention_pathways.get(recommendation.intervention_name, [])
    if not codes:
        return 0.0
    scores = [a.activation_score for a in pathway_activations if a.pathway_code in codes]
    return sum(scores) / len(scores) if scores else 0.0


def _biomarker_relevance(
    recommendation: ScoredRecommendation,
    pathway_activations: list[PathwayActivation],
    intervention_pathways: dict[str, list[str]],
    total_abnormal: int,
) -> float:
    if total_abnormal == 0:
        return 0.0
    codes = set(intervention_pathways.get(recommendation.intervention_name, []))
    biomarkers: set[str] = set()
    for activation in pathway_activations:
        if activation.pathway_code in codes:
            biomarkers.update(activation.contributing_biomarkers)
    return min(len(biomarkers) / total_abnormal, 1.0)


def score_confidence(
    recommendation: ScoredRecommendation,
    evidence_snippets: list[EvidenceSnippet],
    pathway_activations: list[PathwayActivation],
    intervention_pathways: dict[str, list[str]],
    total_abnormal_biomarkers: int,
) -> float:
    """score = 0.35*evidence_strength + 0.25*study_quality + 0.20*biomarker_relevance
    + 0.10*pathway_relevance + 0.10*(1 - safety_risk)"""
    evidence_by_id = {e.external_id: e for e in evidence_snippets}

    evidence_strength = _EVIDENCE_STRENGTH[recommendation.evidence_level]
    study_quality = _study_quality(recommendation, evidence_by_id)
    biomarker_relevance = _biomarker_relevance(
        recommendation, pathway_activations, intervention_pathways, total_abnormal_biomarkers
    )
    pathway_relevance = _pathway_relevance(recommendation, pathway_activations, intervention_pathways)
    safety_deduction = _SAFETY_RISK_SCORE[recommendation.safety_risk]

    score = (
        0.35 * evidence_strength
        + 0.25 * study_quality
        + 0.20 * biomarker_relevance
        + 0.10 * pathway_relevance
        + 0.10 * (1 - safety_deduction)
    )
    return round(min(max(score, 0.0), 1.0), 4)


def determine_evidence_tier(
    recommendation: ScoredRecommendation, evidence_by_id: dict[str, EvidenceSnippet]
) -> EvidenceTier:
    """Derive the user-facing evidence tier from the studies actually cited for this
    recommendation -- never asserted by the LLM, so it can't drift from what was really
    retrieved. Established/Emerging/Preclinical/Research Hypothesis are the only tiers ever
    assigned here: Traditional Use and Historical/Ethnobotanical are reserved for a future
    traditional-medicine evidence source that HerbaGraph does not currently retrieve from."""
    cited = [evidence_by_id[cid] for cid in recommendation.cited_study_ids if cid in evidence_by_id]
    if not cited:
        return EvidenceTier.RESEARCH_HYPOTHESIS

    if any(e.study_type in (StudyType.META_ANALYSIS, StudyType.SYSTEMATIC_REVIEW) for e in cited):
        return EvidenceTier.ESTABLISHED

    rct_count = sum(1 for e in cited if e.study_type == StudyType.RCT)
    if rct_count >= 2:
        return EvidenceTier.ESTABLISHED
    if rct_count == 1:
        return EvidenceTier.EMERGING

    if any(e.study_type in (StudyType.COHORT, StudyType.CASE_CONTROL) for e in cited):
        return EvidenceTier.EMERGING

    if all(e.study_type == StudyType.PRECLINICAL for e in cited):
        return EvidenceTier.PRECLINICAL

    return EvidenceTier.RESEARCH_HYPOTHESIS


def _measured_biomarker_rows(
    normalized_labs: list[NormalizedLabResult],
    custom_biomarkers: list[dict] | None = None,
) -> list[dict]:
    from app.pipeline.user_biomarker_profile import is_catalog_biomarker, is_profile_biomarker

    rows = []
    for lab in sorted(normalized_labs, key=lambda x: x.biomarker_name):
        in_catalog = is_catalog_biomarker(lab.biomarker_name)
        rows.append(
            {
                "biomarker_name": lab.biomarker_name,
                "value": lab.value,
                "unit": lab.unit,
                "status": lab.status.value,
                "category": lab.category,
                "qualitative_label": lab.qualitative_label,
                "expected_label": lab.expected_label,
                "reference_range_low": lab.reference_range_low,
                "reference_range_high": lab.reference_range_high,
                "in_catalog": in_catalog,
                "in_profile": is_profile_biomarker(lab.biomarker_name, custom_biomarkers) if not in_catalog else False,
            }
        )
    return rows


def _biomarker_summary(
    normalized_labs: list[NormalizedLabResult],
    custom_biomarkers: list[dict] | None = None,
    *,
    integrated_analysis: dict | None = None,
) -> dict:
    total = len(normalized_labs)
    abnormal = [lab for lab in normalized_labs if lab.status.value not in ("normal", "optimal")]
    normal = total - len(abnormal)
    categories: dict[str, int] = {}
    for lab in abnormal:
        if lab.category:
            categories[lab.category] = categories.get(lab.category, 0) + 1
    summary = {
        "total_biomarkers": total,
        "abnormal_count": len(abnormal),
        "normal_count": normal,
        "categories_affected": categories,
        "measured_biomarkers": _measured_biomarker_rows(normalized_labs, custom_biomarkers),
    }
    if integrated_analysis:
        summary["integrated_analysis"] = integrated_analysis
    return summary


def _biomarker_interpretations(normalized_labs: list[NormalizedLabResult]) -> list[dict]:
    """Plain-language, per-biomarker interpretation -- the "Biomarker interpretation" output,
    distinct from the aggregate counts in _biomarker_summary. Deterministic/template-based
    (not an extra LLM call) so it never depends on network availability."""
    _INFECTION_INTERPRETATIONS: dict[str, str] = {
        "H. pylori Urea Breath Test": (
            "H. pylori urea breath test was positive, suggesting active gastric colonization. "
            "This is associated with chronic gastritis, peptic ulcer disease, and altered gastric inflammation pathways. "
            "Discuss eradication therapy and follow-up testing with a clinician."
        ),
        "H. pylori Stool Antigen": (
            "H. pylori stool antigen was detected, indicating active infection. "
            "Discuss confirmatory testing and treatment options with a clinician."
        ),
        "Hepatitis B Surface Antigen": (
            "Hepatitis B surface antigen was reactive, suggesting active hepatitis B infection. "
            "Urgent clinician follow-up is recommended."
        ),
        "Hepatitis C Antibody": (
            "Hepatitis C antibody was reactive. Confirmatory RNA testing and hepatology follow-up may be indicated."
        ),
        "HIV Ag/Ab 4th Gen": (
            "HIV antigen/antibody screen was reactive. Confirmatory testing and immediate clinician follow-up are recommended."
        ),
        "Chlamydia trachomatis RNA": (
            "Chlamydia trachomatis nucleic acid test was detected. Treatment and partner notification should be discussed with a clinician."
        ),
        "Neisseria gonorrhoeae RNA": (
            "Neisseria gonorrhoeae nucleic acid test was detected. Antibiotic treatment per current guidelines should be discussed with a clinician."
        ),
        "RPR Syphilis Screen": (
            "Syphilis screening test was reactive. Confirmatory testing and treatment evaluation are recommended."
        ),
    }

    interpretations = []
    for lab in normalized_labs:
        status = lab.status.value
        if status in ("normal", "optimal"):
            continue
        if lab.qualitative_label and lab.biomarker_name in _INFECTION_INTERPRETATIONS:
            interpretation = _INFECTION_INTERPRETATIONS[lab.biomarker_name]
        elif lab.qualitative_label:
            interpretation = (
                f"{lab.biomarker_name} result was {lab.qualitative_label} (expected negative/not detected). "
                "This may activate infection-associated inflammatory pathways discussed below. "
                "This is a laboratory observation, not a diagnosis. Confirm with a clinician."
            )
        else:
            phrase = _BIOMARKER_STATUS_PHRASES.get(status, status)
            interpretation = (
                f"{lab.biomarker_name} is {phrase} ({lab.value}"
                + (f" {lab.unit}" if lab.unit else "")
                + "), which may be relevant to the biological pathways discussed below. "
                "This is a lab-value observation, not a diagnosis."
            )
        interpretations.append(
            {
                "biomarker_name": lab.biomarker_name,
                "status": status,
                "interpretation": interpretation,
            }
        )
    return interpretations


def _executive_summary(biomarker_pattern_analysis: str, biomarker_summary: dict) -> str:
    integrated = biomarker_summary.get("integrated_analysis") or {}
    prefix = ""
    if integrated.get("banner"):
        prefix = integrated["banner"] + ". "

    if biomarker_pattern_analysis:
        return prefix + biomarker_pattern_analysis
    if biomarker_summary["abnormal_count"] == 0 and biomarker_summary["total_biomarkers"] > 0:
        return (
            prefix
            + f"Parsed {biomarker_summary['total_biomarkers']} key biomarkers from your lab report. "
            "All tracked values are within reference ranges. No pathway-specific interventions were flagged."
        )
    if biomarker_summary["abnormal_count"] == 0:
        return prefix + "No biomarkers were parsed from this lab report."
    return (
        prefix
        + f"Your labs show {biomarker_summary['abnormal_count']} of {biomarker_summary['total_biomarkers']} "
        "biomarkers outside their reference range, implicating one or more biological pathways addressed below."
    )


def generate_report(
    normalized_labs: list[NormalizedLabResult],
    pathway_activations: list[PathwayActivation],
    evidence_snippets: list[EvidenceSnippet],
    safety_report: SafetyReport,
    biomarker_pattern_analysis: str,
    clinician_questions: list[str],
    intervention_pathways: dict[str, list[str]],
    *,
    medication_context: dict | None = None,
    lab_trends: dict | None = None,
    routing: RecommendationRoutingContext | None = None,
    custom_biomarkers: list[dict] | None = None,
    health_profile: dict | None = None,
    integrated_analysis: dict | None = None,
    graph_food_sources_by_intervention: dict[str, list[dict]] | None = None,
) -> dict:
    """Stage 8 entry point: score, rank, and assemble the final report payload (pre-persistence)."""
    biomarker_summary = _biomarker_summary(
        normalized_labs,
        custom_biomarkers,
        integrated_analysis=integrated_analysis,
    )
    evidence_by_id = {e.external_id: e for e in evidence_snippets}
    graph_food_map = graph_food_sources_by_intervention or {}

    explainability_list, report_versioning = build_explainability_bundle(
        safety_report.approved_recommendations,
        evidence_snippets,
        pathway_activations,
        intervention_pathways,
        normalized_labs,
        health_profile,
    )
    explainability_by_name = {e.intervention_name: e for e in explainability_list}

    scored: list[ScoredRecommendation] = []
    for rec in safety_report.approved_recommendations:
        explainability = explainability_by_name.get(rec.intervention_name)
        base_confidence = (
            explainability.evidence_confidence_numeric
            if explainability
            else score_confidence(rec, evidence_snippets, pathway_activations, intervention_pathways, biomarker_summary["abnormal_count"])
        )
        confidence = adjusted_confidence(base_confidence, rec.safety_risk)
        tier_rec = rec
        if explainability and explainability.supporting_study_ids:
            tier_rec = rec.model_copy(update={"cited_study_ids": explainability.supporting_study_ids})
        evidence_tier = determine_evidence_tier(tier_rec, evidence_by_id)
        category = rec.category.value if hasattr(rec.category, "value") else str(rec.category)
        food_sources, linked_compound = attach_food_sources(
            rec.intervention_name,
            category,
            graph_food_sources=graph_food_map.get(rec.intervention_name),
        )
        abnormal_names = {
            lab.biomarker_name
            for lab in normalized_labs
            if lab.status.value in ("critical_low", "low", "high", "critical_high")
        }
        rec_intent = intent_for_intervention(rec.intervention_name, abnormal_names)
        narrative = build_intervention_narrative(
            rec.intervention_name,
            category,
            rec.mechanism,
            pathway_activations,
            intervention_pathways,
            normalized_labs,
            food_sources,
            linked_compound=linked_compound,
            recommendation_intent=rec_intent,
            routing=routing,
        )
        canonical_study_ids = (
            explainability.supporting_study_ids
            if explainability
            else rec.cited_study_ids
        )
        rec = rec.model_copy(
            update={
                "confidence_score": confidence,
                "cited_study_ids": canonical_study_ids,
                "cited_urls": [
                    lit.url
                    for lit in (explainability.supporting_literature if explainability else [])
                    if lit.url
                ]
                or [
                    e.url
                    for e in evidence_snippets
                    if e.external_id in canonical_study_ids and e.url
                ],
                "food_sources": food_sources,
                "intervention_narrative": narrative,
                "evidence_tier": evidence_tier,
                "evidence_tier_label": EVIDENCE_TIER_LABELS[evidence_tier],
                "explainability": explainability,
            }
        )
        scored.append(rec)

    abnormal_names = {
        lab.biomarker_name
        for lab in normalized_labs
        if lab.status.value in ("critical_low", "low", "high", "critical_high")
    }
    pathway_index = {
        p.pathway_code: p.model_dump(mode="json")
        for p in pathway_activations
        if p.activation_score > 0
    }

    def _biology_first_sort_key(rec: ScoredRecommendation) -> tuple:
        rec_dict = rec.model_dump(mode="json")
        network_score = biology_first_network_score(
            rec_dict,
            intervention_pathways,
            pathway_index,
            abnormal_names,
            display_intent=classify_display_intent(rec_dict, abnormal_names),
        )
        return (
            rec.safety_profile.requires_prominent_warning if rec.safety_profile else False,
            -network_score,
            -(rec.confidence_score or 0.0),
        )

    scored.sort(key=_biology_first_sort_key)

    ranked_recommendations = []
    for rank, rec in enumerate(scored, start=1):
        ranked_recommendations.append({**rec.model_dump(mode="json"), "rank": rank})

    overall_confidence = (
        round(sum(r["confidence_score"] for r in ranked_recommendations) / len(ranked_recommendations), 4)
        if ranked_recommendations
        else 0.0
    )

    cited_ids: set[str] = set()
    for rec in scored:
        if rec.explainability:
            cited_ids.update(rec.explainability.supporting_study_ids)
        cited_ids.update(rec.cited_study_ids)
    citations = [
        {
            "id": e.external_id,
            "source": e.source.value,
            "title": e.title,
            "year": e.year,
            "study_type": e.study_type.value if e.study_type else None,
            "quality_score": e.quality_score,
            "url": resolve_study_url(
                e.external_id,
                source=e.source.value,
                url=e.url,
            ),
        }
        for e in evidence_snippets
        if e.external_id in cited_ids
    ]
    # dedupe citations by id, preserving first occurrence
    seen_ids: set[str] = set()
    deduped_citations = []
    for citation in citations:
        if citation["id"] in seen_ids:
            continue
        seen_ids.add(citation["id"])
        deduped_citations.append(citation)

    high_risk_names = [
        rec.intervention_name
        for rec in scored
        if rec.safety_risk in (SafetyRiskLevel.MODERATE, SafetyRiskLevel.HIGH)
    ]

    pathway_payload = [p.model_dump(mode="json") for p in pathway_activations]
    systems_base = compute_biological_systems(pathway_activations)
    biological_hierarchy = build_biological_hierarchy(
        biomarker_summary,
        systems_base,
        pathway_payload,
        ranked_recommendations,
        intervention_pathways,
    )
    dual_clinical_rankings = build_dual_clinical_rankings(
        biomarker_summary,
        systems_base,
        pathway_payload,
        ranked_recommendations,
        intervention_pathways,
    )
    executive_summary = _executive_summary(biomarker_pattern_analysis, biomarker_summary)
    recommendation_tiers = build_recommendation_tiers(
        ranked_recommendations,
        biomarker_summary,
        systems_base,
        executive_summary=executive_summary,
        intervention_pathways=intervention_pathways,
        pathway_activations=pathway_payload,
    )
    summary_recommendations = (
        recommendation_tiers["top_considerations"] or ranked_recommendations[:10]
    )
    insights = build_report_insights(
        biomarker_summary,
        systems_base,
        pathway_payload,
        summary_recommendations,
        explainability_items=explainability_list,
        citations=deduped_citations,
    )
    insights["recommendation_tiers"] = recommendation_tiers
    insights["biological_hierarchy"] = biological_hierarchy
    insights["dual_clinical_rankings"] = dual_clinical_rankings
    clinical_summary_hero = build_clinical_summary_hero(
        dual_clinical_rankings,
        insights.get("overall_confidence_assessment"),
        biomarker_summary,
    )
    insights["clinical_summary_hero"] = clinical_summary_hero
    condition_aligned = build_condition_aligned(
        health_profile,
        biomarker_summary,
    )
    insights["condition_aligned"] = condition_aligned

    return {
        "overall_confidence": overall_confidence,
        "model_version": MODEL_VERSION,
        "report_versioning": report_versioning.model_dump(mode="json"),
        "executive_summary": executive_summary,
        "recommendation_tiers": recommendation_tiers,
        "biological_hierarchy": biological_hierarchy,
        "dual_clinical_rankings": dual_clinical_rankings,
        "clinical_summary_hero": clinical_summary_hero,
        "condition_aligned": condition_aligned,
        "biomarker_summary": biomarker_summary,
        "biomarker_interpretations": _biomarker_interpretations(normalized_labs),
        "pathway_activations": pathway_payload,
        "biological_systems": insights["biological_systems"],
        "evidence_summary": insights["evidence_summary"],
        "missing_information": insights["missing_information"],
        "overall_confidence_assessment": insights["overall_confidence_assessment"],
        "biological_reasoning_summary": insights["biological_reasoning_summary"],
        "differential_explanations": insights["differential_explanations"],
        "patient_evidence_gaps": insights["patient_evidence_gaps"],
        "report_methodology": insights["report_methodology"],
        "report_insights": insights,
        "recommendations": ranked_recommendations,
        "citations": deduped_citations,
        "clinician_questions": clinician_questions,
        "safety_summary": {
            "overall_note": safety_report.overall_note,
            "requires_clinician_review": safety_report.requires_clinician_review,
            "high_risk_interventions": high_risk_names,
        },
        "medication_context": medication_context or {"has_medications": False, "notes": [], "biomarker_specific_notes": []},
        "lab_trends": lab_trends or {"has_prior_labs": False, "trends": [], "summary": "No prior lab upload found for trend comparison."},
        "disclaimer": DISCLAIMER,
    }
