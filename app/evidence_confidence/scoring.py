"""Transparent confidence scoring — structured evidence only, never LLM."""

from __future__ import annotations

from datetime import UTC, datetime

from app.evidence_confidence.constants import (
    CONFIDENCE_HIGH_THRESHOLD,
    CONFIDENCE_MODERATE_THRESHOLD,
    GRAPH_LINK_FULL_COUNT,
    RECENCY_DECAY_YEARS,
    RECENCY_FULL_YEARS,
    STUDY_TYPE_CONFIDENCE_CAP,
)
from app.models.enums import EvidenceConfidenceLevel, StudyType
from app.schemas.explainability import ConfidenceFactor
from app.schemas.pipeline import EvidenceSnippet, PathwayActivation


def _study_type_key(study_type: StudyType | None) -> str:
    if study_type is None:
        return "preclinical"
    return study_type.value


_NEGATIVE_KEYWORDS = (
    "no significant",
    "not significant",
    "failed to",
    "no effect",
    "no difference",
    "worsened",
    "increased adverse",
)


def classify_study_outcome(snippet: EvidenceSnippet) -> str:
    """Infer positive/neutral/negative from quality score and abstract keywords."""
    abstract = (snippet.abstract_snippet or "").lower()
    if any(kw in abstract for kw in _NEGATIVE_KEYWORDS):
        return "negative"
    if snippet.quality_score >= 0.55:
        return "positive"
    if snippet.quality_score >= 0.35:
        return "neutral"
    return "negative"


def _count_by_type(cited: list[EvidenceSnippet]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for e in cited:
        key = _study_type_key(e.study_type)
        counts[key] = counts.get(key, 0) + 1
    return counts


def _recency_score(cited: list[EvidenceSnippet], current_year: int) -> float:
    years = [e.year for e in cited if e.year]
    if not years:
        return 0.3
    newest = max(years)
    age = current_year - newest
    if age <= RECENCY_FULL_YEARS:
        return 1.0
    if age >= RECENCY_DECAY_YEARS:
        return 0.2
    return round(1.0 - (age - RECENCY_FULL_YEARS) / (RECENCY_DECAY_YEARS - RECENCY_FULL_YEARS) * 0.8, 4)


def _consistency_score(cited: list[EvidenceSnippet]) -> float:
    if not cited:
        return 0.0
    outcomes = [classify_study_outcome(e) for e in cited]
    positive = outcomes.count("positive")
    return round(positive / len(outcomes), 4)


def _biological_plausibility(
    pathway_count: int,
    biomarker_count: int,
    has_mechanism: bool,
    target_count: int,
) -> float:
    link_count = pathway_count + biomarker_count + (1 if has_mechanism else 0) + min(target_count, 2)
    return round(min(link_count / GRAPH_LINK_FULL_COUNT, 1.0), 4)


def _graph_connectivity(pathway_count: int, biomarker_count: int, target_count: int) -> float:
    links = pathway_count + biomarker_count + target_count
    return round(min(links / GRAPH_LINK_FULL_COUNT, 1.0), 4)


def _study_type_contribution(counts: dict[str, int]) -> tuple[float, list[ConfidenceFactor]]:
    factors: list[ConfidenceFactor] = []
    total = 0.0
    for study_type, count in sorted(counts.items()):
        cap = STUDY_TYPE_CONFIDENCE_CAP.get(study_type, 0.02)
        # Diminishing returns: first study full cap, additional at 50%.
        raw = min(cap + (count - 1) * cap * 0.5, cap * 2) if count else 0.0
        raw = min(raw, 1.0)
        weight = cap
        factors.append(
            ConfidenceFactor(
                factor=f"study_count_{study_type}",
                weight=weight,
                raw_score=round(min(count / 3, 1.0), 4),
                weighted_contribution=round(raw, 4),
                explanation=f"{count} {study_type.replace('_', ' ')} study/studies in cited evidence.",
            )
        )
        total += raw
    return round(min(total, 0.45), 4), factors


def compute_confidence_score(
    cited: list[EvidenceSnippet],
    pathway_count: int,
    biomarker_count: int,
    has_mechanism: bool,
    target_count: int,
    safety_data_available: bool,
    *,
    current_year: int | None = None,
) -> tuple[float, EvidenceConfidenceLevel, list[ConfidenceFactor], float]:
    """Return numeric score, level, factor breakdown, and contradictory penalty."""
    current_year = current_year or datetime.now(UTC).year
    factors: list[ConfidenceFactor] = []

    counts = _count_by_type(cited)
    study_contrib, study_factors = _study_type_contribution(counts)
    factors.extend(study_factors)

    recency_raw = _recency_score(cited, current_year)
    factors.append(
        ConfidenceFactor(
            factor="publication_recency",
            weight=0.08,
            raw_score=recency_raw,
            weighted_contribution=round(0.08 * recency_raw, 4),
            explanation="Recency of newest cited publication.",
        )
    )

    consistency_raw = _consistency_score(cited)
    factors.append(
        ConfidenceFactor(
            factor="consistency_across_studies",
            weight=0.10,
            raw_score=consistency_raw,
            weighted_contribution=round(0.10 * consistency_raw, 4),
            explanation="Share of cited studies with positive directional findings.",
        )
    )

    plaus_raw = _biological_plausibility(pathway_count, biomarker_count, has_mechanism, target_count)
    factors.append(
        ConfidenceFactor(
            factor="biological_plausibility",
            weight=0.12,
            raw_score=plaus_raw,
            weighted_contribution=round(0.12 * plaus_raw, 4),
            explanation="Coherence of biomarker → pathway → mechanism → intervention chain.",
        )
    )

    graph_raw = _graph_connectivity(pathway_count, biomarker_count, target_count)
    factors.append(
        ConfidenceFactor(
            factor="knowledge_graph_connectivity",
            weight=0.10,
            raw_score=graph_raw,
            weighted_contribution=round(0.10 * graph_raw, 4),
            explanation="Number of graph-linked biomarkers, pathways, and molecular targets.",
        )
    )

    quantity_raw = min(len(cited) / 5, 1.0) if cited else 0.0
    factors.append(
        ConfidenceFactor(
            factor="evidence_quantity",
            weight=0.05,
            raw_score=round(quantity_raw, 4),
            weighted_contribution=round(0.05 * quantity_raw, 4),
            explanation=f"{len(cited)} studies cited for this recommendation.",
        )
    )

    mean_quality = sum(e.quality_score for e in cited) / len(cited) if cited else 0.0
    factors.append(
        ConfidenceFactor(
            factor="evidence_quality",
            weight=0.10,
            raw_score=round(mean_quality, 4),
            weighted_contribution=round(0.10 * mean_quality, 4),
            explanation="Mean quality score of cited studies (retriever-assigned).",
        )
    )

    safety_raw = 1.0 if safety_data_available else 0.4
    factors.append(
        ConfidenceFactor(
            factor="safety_data_availability",
            weight=0.05,
            raw_score=safety_raw,
            weighted_contribution=round(0.05 * safety_raw, 4),
            explanation="Whether safety flags or interaction data exist in the knowledge graph.",
        )
    )

    contradiction_penalty = round((1.0 - consistency_raw) * 0.15, 4)
    if contradiction_penalty > 0:
        factors.append(
            ConfidenceFactor(
                factor="contradictory_evidence_penalty",
                weight=-0.15,
                raw_score=round(1.0 - consistency_raw, 4),
                weighted_contribution=-contradiction_penalty,
                explanation="Penalty for neutral/negative findings among cited studies.",
            )
        )

    numeric = round(
        min(
            max(
                study_contrib
                + sum(f.weighted_contribution for f in factors if f.factor != "contradictory_evidence_penalty")
                - contradiction_penalty,
                0.0,
            ),
            1.0,
        ),
        4,
    )

    if numeric >= CONFIDENCE_HIGH_THRESHOLD:
        level = EvidenceConfidenceLevel.HIGH
    elif numeric >= CONFIDENCE_MODERATE_THRESHOLD:
        level = EvidenceConfidenceLevel.MODERATE
    else:
        level = EvidenceConfidenceLevel.LOW

    return numeric, level, factors, contradiction_penalty


def supporting_pathway_confidence(activation_score: float) -> EvidenceConfidenceLevel:
    if activation_score >= 0.65:
        return EvidenceConfidenceLevel.HIGH
    if activation_score >= 0.35:
        return EvidenceConfidenceLevel.MODERATE
    return EvidenceConfidenceLevel.LOW


def biomarker_contribution_strength(
    biomarker: str,
    pathway_activations: list[PathwayActivation],
    intervention_pathway_codes: set[str],
) -> float:
    scores = []
    for activation in pathway_activations:
        if activation.pathway_code not in intervention_pathway_codes:
            continue
        if biomarker in activation.contributing_biomarkers:
            scores.append(activation.activation_score)
    return round(max(scores) if scores else 0.5, 4)