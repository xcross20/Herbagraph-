"""Evidence Confidence & Explainability Engine — main entry point."""

from __future__ import annotations

from datetime import UTC, datetime

from app.evidence_confidence.catalog_fallbacks import (
    catalog_pathway_codes,
    catalog_why_surfaced,
    pathway_display_name,
)
from app.evidence_confidence.catalog_lookup import lookup_intervention, molecular_targets_for
from app.evidence_confidence.citations import build_supporting_literature, resolve_cited_studies
from app.evidence_confidence.constants import (
    EVIDENCE_VERSION,
    EXPLAINABILITY_ENGINE_VERSION,
    KNOWLEDGE_GRAPH_VERSION,
    REASONING_ENGINE_VERSION,
    REPORT_GENERATION_VERSION,
    current_generation_timestamp,
)
from app.evidence_confidence.display import (
    evidence_display_label,
    evidence_synthesis_statement,
    intervention_classes,
)
from app.evidence_confidence.quality import grade_evidence_quality
from app.evidence_confidence.decomposition import decompose_confidence
from app.evidence_confidence.scoring import (
    biomarker_contribution_strength,
    classify_study_outcome,
    compute_confidence_score,
    supporting_pathway_confidence,
)
from app.models.enums import (
    EVIDENCE_CONFIDENCE_LABELS,
    EVIDENCE_QUALITY_LABELS,
    EvidenceConfidenceLevel,
    EvidenceQualityGrade,
    StudyOutcome,
    StudyType,
)
from app.schemas.explainability import (
    ContradictoryEvidence,
    EvidencePassport,
    EvidenceTimelineEntry,
    ExplanationChainLink,
    GraphProvenance,
    MolecularTarget,
    PopulationApplicability,
    RecommendationExplainability,
    ReportVersioning,
    ResearchGap,
    StudyOutcomeSummary,
    SupportingBiomarker,
    SupportingLiteratureEntry,
    SupportingPathway,
)
from app.schemas.pipeline import (
    EvidenceSnippet,
    LLMRecommendation,
    NormalizedLabResult,
    PathwayActivation,
)


def build_report_versioning() -> ReportVersioning:
    return ReportVersioning(
        knowledge_graph_version=KNOWLEDGE_GRAPH_VERSION,
        evidence_version=EVIDENCE_VERSION,
        reasoning_engine_version=REASONING_ENGINE_VERSION,
        explainability_engine_version=EXPLAINABILITY_ENGINE_VERSION,
        report_generation_version=REPORT_GENERATION_VERSION,
        date_generated=current_generation_timestamp(),
    )


def _timeline_label(study_type: str | None, year: int) -> str:
    labels = {
        "meta_analysis": "Meta-analysis",
        "systematic_review": "Systematic review",
        "rct": "Human RCT",
        "cohort": "Prospective cohort study",
        "case_control": "Case-control study",
        "mechanistic": "Mechanistic study",
        "preclinical": "Preclinical study",
        "animal": "Animal study",
        "in_vitro": "In vitro study",
    }
    base = labels.get(study_type or "", "Study published")
    return f"{base} ({year})"


def _build_timeline(cited: list[EvidenceSnippet]) -> list[EvidenceTimelineEntry]:
    dated = [e for e in cited if e.year]
    dated.sort(key=lambda e: e.year or 0)
    entries: list[EvidenceTimelineEntry] = []
    seen_types: set[str] = set()
    for e in dated:
        st = e.study_type.value if e.study_type else "study"
        if st in seen_types and len(entries) >= 4:
            continue
        seen_types.add(st)
        entries.append(
            EvidenceTimelineEntry(
                year=e.year or 0,
                label=_timeline_label(st, e.year or 0),
                study_id=e.external_id,
                study_type=st,
            )
        )
    return entries


def _build_contradictory(cited: list[EvidenceSnippet]) -> ContradictoryEvidence:
    if not cited:
        return ContradictoryEvidence(
            positive_percent=0.0,
            neutral_percent=0.0,
            negative_percent=0.0,
            disagreement_summary="No cited studies available to assess agreement.",
        )
    studies = []
    counts = {"positive": 0, "neutral": 0, "negative": 0}
    for e in cited:
        outcome = classify_study_outcome(e)
        counts[outcome] += 1
        studies.append(
            StudyOutcomeSummary(
                study_id=e.external_id,
                title=e.title,
                outcome=StudyOutcome(outcome),
                year=e.year,
                study_type=e.study_type.value if e.study_type else None,
            )
        )
    total = len(cited)
    pos_pct = round(counts["positive"] / total * 100, 1)
    neu_pct = round(counts["neutral"] / total * 100, 1)
    neg_pct = round(counts["negative"] / total * 100, 1)
    if neg_pct > 20:
        summary = (
            f"{neg_pct:.0f}% of cited studies show neutral or negative findings. "
            "Clinicians should weigh conflicting evidence before acting."
        )
    elif neu_pct > 25:
        summary = f"{neu_pct:.0f}% of cited studies are directionally neutral — effect size may be modest."
    else:
        summary = f"{pos_pct:.0f}% of cited studies support the recommended direction."
    return ContradictoryEvidence(
        positive_count=counts["positive"],
        neutral_count=counts["neutral"],
        negative_count=counts["negative"],
        positive_percent=pos_pct,
        neutral_percent=neu_pct,
        negative_percent=neg_pct,
        disagreement_summary=summary,
        studies=studies,
    )


def _build_population(
    cited: list[EvidenceSnippet],
    health_profile: dict,
    typical_dose: str | None,
) -> PopulationApplicability:
    notes: list[str] = []
    sample_sizes: list[int] = []
    countries: list[str] = []
    durations: list[str] = []
    doses: list[str] = []
    disease_states: list[str] = []

    for e in cited:
        abstract = (e.abstract_snippet or "").lower()
        if "n=" in abstract or "n =" in abstract:
            notes.append(f"Sample size mentioned in {e.external_id}")
        if "diabetes" in abstract:
            disease_states.append("diabetes")
        if "obesity" in abstract or "bmi" in abstract:
            notes.append("BMI/obesity population mentioned")
        if "week" in abstract or "month" in abstract:
            durations.append(f"Duration noted in {e.external_id}")
        if "mg" in abstract or "g/day" in abstract:
            doses.append(f"Dose noted in {e.external_id}")

    if typical_dose:
        doses.append(typical_dose)

    return PopulationApplicability(
        age_range=health_profile.get("age_range"),
        sex=health_profile.get("biological_sex"),
        disease_states=sorted(set(disease_states)),
        bmi_notes=notes,
        sample_sizes=sample_sizes,
        countries=countries,
        treatment_durations=durations,
        doses=doses,
        extraction_notes=[
            "Population fields are best-effort from abstracts and patient profile; "
            "full structured extraction is planned for evidence v2."
        ],
    )


def _detect_research_gaps(
    cited: list[EvidenceSnippet],
    health_profile: dict,
    abnormal_biomarkers: set[str],
    pathway_codes: set[str],
) -> list[ResearchGap]:
    gaps: list[ResearchGap] = []
    rct_count = sum(1 for e in cited if e.study_type and e.study_type.value == "rct")
    if rct_count < 2:
        gaps.append(ResearchGap(gap="Limited human RCTs", severity="high" if rct_count == 0 else "moderate"))
    if rct_count > 0 and all((e.quality_score or 0) < 0.5 for e in cited if e.study_type and e.study_type.value == "rct"):
        gaps.append(ResearchGap(gap="Small sample sizes in available RCTs", severity="moderate"))

    titles_abstracts = " ".join(
        (e.title + " " + (e.abstract_snippet or "")).lower() for e in cited
    )
    if "pediatric" not in titles_abstracts and "children" not in titles_abstracts:
        gaps.append(ResearchGap(gap="No pediatric studies identified", severity="moderate"))
    if "pregnan" not in titles_abstracts:
        gaps.append(ResearchGap(gap="No pregnancy studies identified", severity="moderate"))
    if "long-term" not in titles_abstracts and "year" not in titles_abstracts:
        gaps.append(ResearchGap(gap="Limited long-term follow-up evidence", severity="low"))

    known_conditions = health_profile.get("known_conditions") or []
    if "ckd" in " ".join(known_conditions).lower() and "kidney" not in titles_abstracts:
        gaps.append(ResearchGap(gap="Few CKD-specific studies", severity="moderate"))

    # Missing biomarkers that commonly inform the same pathways
    _PATHWAY_EXPECTED: dict[str, list[str]] = {
        "NF_KB": ["CRP", "hs-CRP"],
        "INSULIN_PI3K_AKT": ["Insulin", "Glucose", "HbA1c"],
        "HEPATIC_LIPID": ["ALT", "AST", "Triglycerides"],
    }
    for code in pathway_codes:
        for expected in _PATHWAY_EXPECTED.get(code, []):
            if expected not in abnormal_biomarkers and expected not in {g.gap for g in gaps}:
                gaps.append(
                    ResearchGap(gap=f"Missing {expected} measurement for pathway context", severity="low")
                )
    return gaps[:8]


def _build_provenance(cited: list[EvidenceSnippet], intervention_name: str) -> list[GraphProvenance]:
    today = datetime.now(UTC).date().isoformat()
    records: list[GraphProvenance] = [
        GraphProvenance(
            source="knowledge_graph",
            knowledge_graph_node=f"intervention:{intervention_name}",
            extraction_date=today,
            review_status="catalog_seeded",
            evidence_version=EVIDENCE_VERSION,
        )
    ]
    for e in cited:
        records.append(
            GraphProvenance(
                source=e.source.value,
                external_id=e.external_id,
                url=e.url,
                extraction_date=today,
                review_status="auto_retrieved",
                evidence_version=EVIDENCE_VERSION,
            )
        )
    return records


def _build_explanation_chain(
    biomarkers: list[SupportingBiomarker],
    pathways: list[SupportingPathway],
    mechanism: str | None,
    intervention_name: str,
    cited: list[EvidenceSnippet],
) -> list[ExplanationChainLink]:
    chain: list[ExplanationChainLink] = []
    for b in biomarkers:
        chain.append(
            ExplanationChainLink(
                link_type="biomarker",
                label=b.biomarker_name,
                detail=f"Status: {b.status or 'abnormal'}; contribution {b.contribution_strength:.0%}",
            )
        )
    for p in pathways:
        chain.append(
            ExplanationChainLink(
                link_type="pathway",
                label=p.pathway_name,
                detail=f"Activation {p.activation_score:.0%}; confidence {p.confidence.value}",
            )
        )
    if mechanism:
        chain.append(ExplanationChainLink(link_type="mechanism", label="Mechanism", detail=mechanism))
    chain.append(
        ExplanationChainLink(
            link_type="intervention",
            label=intervention_name,
            detail="Recommended based on graph-linked biomarker and pathway signals.",
        )
    )
    if cited:
        best = max(cited, key=lambda e: e.quality_score)
        chain.append(
            ExplanationChainLink(
                link_type="evidence",
                label=best.title[:120],
                detail=f"{best.study_type.value if best.study_type else 'study'} ({best.year or 'n.d.'})",
            )
        )
    return chain


def _why_recommended(
    biomarkers: list[SupportingBiomarker],
    pathways: list[SupportingPathway],
    quality_label: str,
    confidence_level: EvidenceConfidenceLevel,
    has_safety_data: bool,
) -> list[str]:
    reasons: list[str] = []
    for b in biomarkers[:3]:
        reasons.append(f"Elevated or abnormal {b.biomarker_name}")
    for p in pathways[:2]:
        reasons.append(f"{p.pathway_name} pathway activated")
    reasons.append(f"{quality_label} quality human evidence")
    reasons.append(f"{EVIDENCE_CONFIDENCE_LABELS[confidence_level]} structured confidence score")
    if has_safety_data:
        reasons.append("Safety profile available in knowledge graph")
    return reasons


_QUALITY_STARS: dict[EvidenceQualityGrade, int] = {
    EvidenceQualityGrade.VERY_HIGH: 5,
    EvidenceQualityGrade.HIGH: 4,
    EvidenceQualityGrade.MODERATE: 3,
    EvidenceQualityGrade.LOW: 2,
    EvidenceQualityGrade.VERY_LOW: 1,
}

_HUMAN_STUDY_TYPES = frozenset({
    StudyType.META_ANALYSIS,
    StudyType.SYSTEMATIC_REVIEW,
    StudyType.RCT,
    StudyType.COHORT,
    StudyType.CASE_CONTROL,
})


def _count_studies(cited: list[EvidenceSnippet]) -> dict[str, int]:
    counts = {
        "meta_analyses": 0,
        "systematic_reviews": 0,
        "rcts": 0,
        "human_studies": 0,
    }
    for e in cited:
        if not e.study_type:
            continue
        if e.study_type == StudyType.META_ANALYSIS:
            counts["meta_analyses"] += 1
            counts["human_studies"] += 1
        elif e.study_type == StudyType.SYSTEMATIC_REVIEW:
            counts["systematic_reviews"] += 1
            counts["human_studies"] += 1
        elif e.study_type == StudyType.RCT:
            counts["rcts"] += 1
            counts["human_studies"] += 1
        elif e.study_type in _HUMAN_STUDY_TYPES:
            counts["human_studies"] += 1
    return counts


def _build_evidence_passport(
    cited: list[EvidenceSnippet],
    quality_grade: EvidenceQualityGrade,
    quality_label: str,
    confidence_level: EvidenceConfidenceLevel,
    contradictory: ContradictoryEvidence,
    population: PopulationApplicability,
    gaps: list[ResearchGap],
    *,
    intervention_name: str,
    category: str,
    why_surfaced: list[str],
    primary_pathway: str | None,
    safety_label: str,
    biomarker_names: list[str],
    evidence_tier_value: str | None = None,
    supporting_literature: list[SupportingLiteratureEntry] | None = None,
) -> EvidencePassport:
    supporting_literature = supporting_literature or []
    counts = _count_studies(cited)
    years = [e.year for e in cited if e.year]
    last_year = max(years) if years else None

    confidence_why: list[str] = []
    if counts["meta_analyses"]:
        confidence_why.append(f"{counts['meta_analyses']} meta-analyses")
    if counts["systematic_reviews"]:
        confidence_why.append(f"{counts['systematic_reviews']} systematic reviews")
    if counts["rcts"]:
        confidence_why.append(f"{counts['rcts']} RCTs")
    if counts["human_studies"]:
        confidence_why.append(f"{counts['human_studies']} human studies")
    if contradictory.negative_count == 0 and contradictory.neutral_count == 0 and cited:
        confidence_why.append("No conflicting evidence in cited studies")
    elif contradictory.negative_percent > 0:
        confidence_why.append(f"{contradictory.negative_percent:.0f}% negative findings among cited studies")

    pop_parts = []
    if population.age_range:
        pop_parts.append(f"Age {population.age_range}")
    if population.sex:
        pop_parts.append(population.sex)
    if population.disease_states:
        pop_parts.append(", ".join(population.disease_states))
    if not pop_parts and cited:
        population_summary = "Adults (from cited study populations — best-effort)"
    else:
        population_summary = "; ".join(pop_parts) if pop_parts else "General adult population (profile not specified)"

    applicable_to: list[str] = ["Adults"]
    if population.age_range:
        applicable_to[0] = f"Age {population.age_range}"
    if population.sex:
        applicable_to.append(population.sex)
    for state in population.disease_states[:2]:
        applicable_to.append(state)
    for biomarker in biomarker_names[:2]:
        status_hint = biomarker.lower()
        if "iron" in status_hint:
            applicable_to.append("Iron deficiency pattern")
        elif "tsh" in status_hint:
            applicable_to.append("Thyroid dysregulation pattern")
        elif "glucose" in status_hint or "hba1c" in status_hint:
            applicable_to.append("Glycemic dysregulation pattern")
    human_study_count = counts["meta_analyses"] + counts["systematic_reviews"] + counts["rcts"] + counts["human_studies"]
    if human_study_count:
        applicable_to.append("Human evidence")
    else:
        applicable_to.append("Limited human evidence")
    applicable_to.append("Not pregnancy specific")

    display_label = evidence_display_label(quality_grade, evidence_tier_value)
    last_updated_display = None
    if last_year:
        last_updated_display = datetime(last_year, 7, 1).strftime("%B %Y")

    passport_gaps = [g.gap for g in gaps[:5]] or ["Insufficient evidence for additional population-specific gaps"]
    if not why_surfaced:
        why_surfaced = ["Insufficient evidence to summarize surfacing rationale"]
    if not primary_pathway:
        primary_pathway = "Insufficient evidence"

    return EvidencePassport(
        quality_stars=_QUALITY_STARS.get(quality_grade, 3),
        quality_label=quality_label,
        confidence_level=confidence_level,
        confidence_label=EVIDENCE_CONFIDENCE_LABELS[confidence_level],
        meta_analyses=counts["meta_analyses"],
        systematic_reviews=counts["systematic_reviews"],
        rcts=counts["rcts"],
        human_studies=counts["human_studies"],
        conflicting_evidence=contradictory.negative_count > 0 or contradictory.neutral_percent > 25,
        population_summary=population_summary or "Not available",
        applicable_to=applicable_to,
        last_updated_year=last_year,
        last_updated_display=last_updated_display,
        research_gaps=passport_gaps,
        confidence_why=confidence_why,
        evidence_display_label=display_label,
        why_surfaced=why_surfaced,
        primary_pathway=primary_pathway,
        safety_label=safety_label,
        evidence_synthesis_statement=evidence_synthesis_statement(
            intervention_name, biomarker_names, display_label
        ),
        intervention_classes=intervention_classes(intervention_name, category),
        supporting_literature=supporting_literature,
    )


def _why_not_higher(
    factors: list,
    gaps: list[ResearchGap],
    confidence_level: EvidenceConfidenceLevel,
) -> list[str]:
    if confidence_level == EvidenceConfidenceLevel.HIGH:
        return []

    reasons: list[str] = []
    for f in factors:
        if f.raw_score < 0.4 and f.factor not in ("contradictory_evidence_penalty",):
            reasons.append(f.explanation)
    for gap in gaps:
        if gap.severity in ("high", "moderate"):
            reasons.append(gap.gap)
    return reasons[:6]


def explain_recommendation(
    recommendation: LLMRecommendation,
    evidence_snippets: list[EvidenceSnippet],
    pathway_activations: list[PathwayActivation],
    intervention_pathways: dict[str, list[str]],
    normalized_labs: list[NormalizedLabResult],
    health_profile: dict | None = None,
    *,
    versioning: ReportVersioning | None = None,
) -> RecommendationExplainability:
    """Build full explainability for one recommendation."""
    health_profile = health_profile or {}
    versioning = versioning or build_report_versioning()
    name = recommendation.intervention_name

    abnormal_labs = {
        lab.biomarker_name: lab
        for lab in normalized_labs
        if lab.status.value in ("critical_low", "low", "high", "critical_high")
    }
    abnormal_names = set(abnormal_labs)

    cited = resolve_cited_studies(recommendation, evidence_snippets)
    supporting_literature = build_supporting_literature(cited)

    pathway_codes = set(intervention_pathways.get(name, []))
    if not pathway_codes:
        pathway_codes = set(catalog_pathway_codes(name, abnormal_names))
    catalog_entry = lookup_intervention(name)
    mechanism = recommendation.mechanism or (catalog_entry or {}).get("mechanism")
    targets_raw = molecular_targets_for(name, pathway_codes)

    supporting_biomarkers: list[SupportingBiomarker] = []
    for biomarker_name in sorted(abnormal_labs):
        strength = biomarker_contribution_strength(biomarker_name, pathway_activations, pathway_codes)
        if strength < 0.35 and biomarker_name not in {
            b for a in pathway_activations if a.pathway_code in pathway_codes for b in a.contributing_biomarkers
        }:
            continue
        lab = abnormal_labs[biomarker_name]
        codes = [
            a.pathway_code
            for a in pathway_activations
            if biomarker_name in a.contributing_biomarkers and a.pathway_code in pathway_codes
        ]
        supporting_biomarkers.append(
            SupportingBiomarker(
                biomarker_name=biomarker_name,
                status=lab.status.value,
                contribution_strength=strength,
                pathway_codes=codes,
            )
        )
    supporting_biomarkers.sort(key=lambda b: b.contribution_strength, reverse=True)

    supporting_pathways: list[SupportingPathway] = []
    for activation in pathway_activations:
        if activation.pathway_code not in pathway_codes:
            continue
        supporting_pathways.append(
            SupportingPathway(
                pathway_code=activation.pathway_code,
                pathway_name=activation.pathway_name,
                activation_score=activation.activation_score,
                confidence=supporting_pathway_confidence(activation.activation_score),
                direction=activation.direction.value,
            )
        )
    supporting_pathways.sort(key=lambda p: p.activation_score, reverse=True)

    if not supporting_pathways and pathway_codes:
        for code in sorted(pathway_codes):
            supporting_pathways.append(
                SupportingPathway(
                    pathway_code=code,
                    pathway_name=pathway_display_name(code),
                    activation_score=0.5,
                    confidence=EvidenceConfidenceLevel.MODERATE,
                    direction=None,
                )
            )

    molecular_targets = [
        MolecularTarget(
            name=t["name"],
            compound=t.get("compound"),
            provenance_node=t.get("provenance_node"),
        )
        for t in targets_raw
    ]

    has_safety_data = bool(
        catalog_entry and ((catalog_entry.get("safety_flags")) or (catalog_entry.get("drug_interactions")))
    )

    numeric, confidence_level, factors, contradiction_penalty = compute_confidence_score(
        cited,
        pathway_count=len(supporting_pathways),
        biomarker_count=len(supporting_biomarkers),
        has_mechanism=bool(mechanism),
        target_count=len(molecular_targets),
        safety_data_available=has_safety_data,
    )

    quality_grade, _, quality_explanation = grade_evidence_quality(cited)
    quality_label = EVIDENCE_QUALITY_LABELS[quality_grade]

    chain = _build_explanation_chain(
        supporting_biomarkers, supporting_pathways, mechanism, name, cited
    )
    rationale_parts = [link.detail or link.label for link in chain]
    biological_rationale = (
        f"{name} recommended because: " + "; ".join(rationale_parts[:5]) + "."
        if rationale_parts
        else f"{name} surfaced from pathway-linked evidence with limited chain data."
    )

    gaps = _detect_research_gaps(
        cited, health_profile, set(abnormal_labs), pathway_codes
    )
    why_rec = _why_recommended(
        supporting_biomarkers, supporting_pathways, quality_label, confidence_level, has_safety_data
    )
    if not why_rec or (not supporting_biomarkers and not supporting_pathways):
        why_rec = catalog_why_surfaced(name, abnormal_names) or why_rec
    elif supporting_biomarkers:
        catalog_reasons = catalog_why_surfaced(name, abnormal_names)
        for reason in catalog_reasons:
            if reason not in why_rec:
                why_rec.insert(0, reason)
    why_not = _why_not_higher(factors, gaps, confidence_level)

    confidence_explanation = (
        f"Structured confidence: {EVIDENCE_CONFIDENCE_LABELS[confidence_level]}. {quality_explanation}"
    )

    contradictory = _build_contradictory(cited)
    population = _build_population(cited, health_profile, recommendation.typical_dose)
    category_val = (
        recommendation.category.value
        if hasattr(recommendation.category, "value")
        else str(recommendation.category)
    )
    primary_pathway = supporting_pathways[0].pathway_name if supporting_pathways else None
    safety_label = getattr(recommendation, "safety_risk", None)
    if safety_label is not None and hasattr(safety_label, "value"):
        safety_label = safety_label.value
    else:
        safety_label = str(safety_label or "low")
    tier_val = getattr(recommendation, "evidence_tier", None)
    if tier_val is not None and hasattr(tier_val, "value"):
        tier_val = tier_val.value
    human_types = {"rct", "meta_analysis", "systematic_review", "cohort", "case_control"}
    cited_human = sum(
        1 for e in cited if (e.study_type.value if e.study_type else "") in human_types
    )
    present_lab_names = [lab.biomarker_name for lab in normalized_labs]
    decomposition = decompose_confidence(
        evidence_numeric=numeric,
        contradiction_penalty=contradiction_penalty,
        supporting_biomarker_names=[b.biomarker_name for b in supporting_biomarkers],
        present_lab_names=present_lab_names,
        pathway_codes=pathway_codes,
        intervention_name=name,
        health_profile=health_profile,
        has_safety_data=has_safety_data,
        has_mechanism=bool(mechanism),
        cited_human_studies=cited_human,
    )
    why_not = why_not or [
        f"{item.action} (~+{item.expected_gain_percent}%)"
        for item in decomposition.gap_analysis[:4]
    ]

    passport = _build_evidence_passport(
        cited,
        quality_grade,
        quality_label,
        confidence_level,
        contradictory,
        population,
        gaps,
        intervention_name=name,
        category=category_val,
        why_surfaced=why_rec[:4],
        primary_pathway=primary_pathway,
        safety_label=safety_label,
        biomarker_names=[b.biomarker_name for b in supporting_biomarkers] or sorted(abnormal_names),
        evidence_tier_value=tier_val,
        supporting_literature=supporting_literature,
    )

    return RecommendationExplainability(
        intervention_name=name,
        evidence_confidence_level=confidence_level,
        evidence_confidence_numeric=numeric,
        evidence_quality_grade=quality_grade,
        confidence_factors=factors,
        biological_rationale=biological_rationale,
        explanation_chain=chain,
        why_recommended=why_rec,
        why_not_higher=why_not,
        confidence_explanation=confidence_explanation,
        confidence_decomposition=decomposition,
        supporting_biomarkers=supporting_biomarkers,
        supporting_pathways=supporting_pathways,
        molecular_targets=molecular_targets,
        supporting_study_ids=[entry.study_id for entry in supporting_literature],
        supporting_literature=supporting_literature,
        evidence_timeline=_build_timeline(cited),
        contradictory_evidence=contradictory,
        population_applicability=population,
        research_gaps=gaps,
        provenance=_build_provenance(cited, name),
        evidence_passport=passport,
        versioning=versioning,
    )


def evaluate_recommendations(
    recommendations: list[LLMRecommendation],
    evidence_snippets: list[EvidenceSnippet],
    pathway_activations: list[PathwayActivation],
    intervention_pathways: dict[str, list[str]],
    normalized_labs: list[NormalizedLabResult],
    health_profile: dict | None = None,
) -> list[RecommendationExplainability]:
    versioning = build_report_versioning()
    return [
        explain_recommendation(
            rec,
            evidence_snippets,
            pathway_activations,
            intervention_pathways,
            normalized_labs,
            health_profile,
            versioning=versioning,
        )
        for rec in recommendations
    ]


def build_explainability_bundle(
    recommendations: list[LLMRecommendation],
    evidence_snippets: list[EvidenceSnippet],
    pathway_activations: list[PathwayActivation],
    intervention_pathways: dict[str, list[str]],
    normalized_labs: list[NormalizedLabResult],
    health_profile: dict | None = None,
) -> tuple[list[RecommendationExplainability], ReportVersioning]:
    versioning = build_report_versioning()
    items = [
        explain_recommendation(
            rec,
            evidence_snippets,
            pathway_activations,
            intervention_pathways,
            normalized_labs,
            health_profile,
            versioning=versioning,
        )
        for rec in recommendations
    ]
    return items, versioning