"""Full graph recommendation engine (knowledge_path=canonical).

Traverses pathway activations → MODULATES edges → intervention entities,
ranks by edge confidence / evidence type / entity tier, and emits pathway→
intervention maps plus graph-backed evidence snippets for Stage 4/5.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.canonical_entity import CanonicalEntity, GraphEdge
from app.models.enums import (
    CanonicalEntityType,
    CoverageTier,
    GraphEvidenceType,
    GraphRelationshipType,
    StudySource,
    StudyType,
)
from app.pipeline.canonical_graph import load_registry_index, normalize_name
from app.pipeline.intervention_catalog import build_interventions_for_routing
from app.pipeline.test_type_router import RecommendationRoutingContext
from app.schemas.pipeline import EvidenceSnippet, NormalizedLabResult, PathwayActivation

_MODULATION_RELS = frozenset(
    {
        GraphRelationshipType.MODULATES.value,
        GraphRelationshipType.INFLUENCES.value,
        GraphRelationshipType.ACTIVATES.value,
        GraphRelationshipType.INHIBITS.value,
        GraphRelationshipType.TARGETS.value,
    }
)

_EVIDENCE_RANK = {
    GraphEvidenceType.META_ANALYTIC.value: 0,
    GraphEvidenceType.CLINICAL_HUMAN.value: 1,
    GraphEvidenceType.OBSERVATIONAL_HUMAN.value: 2,
    GraphEvidenceType.MECHANISTIC.value: 3,
    GraphEvidenceType.ANIMAL.value: 4,
    GraphEvidenceType.PREDICTED.value: 5,
}

_TIER_RANK = {
    CoverageTier.TIER_A.value: 0,
    CoverageTier.TIER_B.value: 1,
    CoverageTier.TIER_C.value: 2,
}

_MAX_PER_PATHWAY = 14


@dataclass
class GraphInterventionHit:
    name: str
    entity_id: str
    pathway_code: str
    relationship: str
    confidence: float
    evidence_type: str
    citation: str | None
    notes: str | None
    coverage_tier: str


def _pathway_entity_ids(session: Session, pathway_codes: set[str]) -> dict[str, object]:
    if not pathway_codes:
        return {}
    rows = list(
        session.execute(
            select(CanonicalEntity).where(
                CanonicalEntity.entity_type == CanonicalEntityType.PATHWAY.value,
                CanonicalEntity.canonical_name.in_(list(pathway_codes)),
            )
        ).scalars().all()
    )
    return {row.canonical_name: row.id for row in rows}


def _load_modulation_hits(
    session: Session,
    pathway_codes: set[str],
) -> list[GraphInterventionHit]:
    path_ids = _pathway_entity_ids(session, pathway_codes)
    if not path_ids:
        return []
    id_to_code = {vid: code for code, vid in path_ids.items()}
    edges = list(
        session.execute(
            select(GraphEdge).where(
                GraphEdge.source_entity_id.in_(list(path_ids.values())),
                GraphEdge.relationship_type.in_(list(_MODULATION_RELS)),
            )
        ).scalars().all()
    )
    if not edges:
        return []
    target_ids = {e.target_entity_id for e in edges}
    targets = {
        t.id: t
        for t in session.execute(
            select(CanonicalEntity).where(CanonicalEntity.id.in_(list(target_ids)))
        ).scalars().all()
    }
    hits: list[GraphInterventionHit] = []
    for edge in edges:
        target = targets.get(edge.target_entity_id)
        if target is None:
            continue
        if target.entity_type in (
            CanonicalEntityType.PATHWAY.value,
            CanonicalEntityType.BIOMARKER.value,
        ):
            continue
        pathway_code = id_to_code.get(edge.source_entity_id, "")
        hits.append(
            GraphInterventionHit(
                name=target.display_name or target.canonical_name,
                entity_id=target.entity_id,
                pathway_code=pathway_code,
                relationship=edge.relationship_type,
                confidence=float(edge.confidence or 0.3),
                evidence_type=edge.evidence_type,
                citation=edge.citation,
                notes=edge.notes,
                coverage_tier=target.coverage_tier,
            )
        )
    return hits


def _rank_hit(hit: GraphInterventionHit) -> tuple:
    return (
        _EVIDENCE_RANK.get(hit.evidence_type, 9),
        _TIER_RANK.get(hit.coverage_tier, 9),
        -hit.confidence,
        hit.name,
    )


def build_interventions_from_graph(
    session: Session,
    routing: RecommendationRoutingContext,
    pathway_activations: list[PathwayActivation],
    normalized_labs: list[NormalizedLabResult],
    *,
    hybrid_legacy_fill: bool = True,
) -> tuple[dict[str, list[str]], dict]:
    """Return pathway_code → ranked intervention names from graph edges.

    When the graph is sparse for a pathway, optionally backfill with legacy
    routing filtered to registry entities (hybrid mode).
    """
    pathway_codes = {a.pathway_code for a in pathway_activations}
    hits = _load_modulation_hits(session, pathway_codes)
    by_pathway: dict[str, list[GraphInterventionHit]] = defaultdict(list)
    for hit in hits:
        if hit.pathway_code:
            by_pathway[hit.pathway_code].append(hit)

    result: dict[str, list[str]] = {}
    best_hit_by_name: dict[str, GraphInterventionHit] = {}
    for code, group in by_pathway.items():
        ranked = sorted(group, key=_rank_hit)
        names: list[str] = []
        seen: set[str] = set()
        for hit in ranked:
            key = normalize_name(hit.name)
            if key in seen:
                continue
            seen.add(key)
            names.append(hit.name)
            prev = best_hit_by_name.get(key)
            if prev is None or _rank_hit(hit) < _rank_hit(prev):
                best_hit_by_name[key] = hit
            if len(names) >= _MAX_PER_PATHWAY:
                break
        if names:
            result[code] = names

    index = load_registry_index(session)
    meta = {
        "knowledge_path": "canonical",
        "engine": "graph_recommendation_engine_v1",
        "registry_entity_count": index.entity_count,
        "graph_hits": len(hits),
        "pathways_with_graph_recs": len(result),
        "hybrid_legacy_fill": hybrid_legacy_fill,
        "legacy_fill_count": 0,
    }

    if hybrid_legacy_fill:
        legacy = build_interventions_for_routing(routing, pathway_activations, normalized_labs)
        for code, names in legacy.items():
            existing = result.setdefault(code, [])
            existing_keys = {normalize_name(n) for n in existing}
            for name in names:
                if index.entity_count and index.resolve(name) is None:
                    continue
                key = normalize_name(name)
                if key in existing_keys:
                    continue
                existing.append(name)
                existing_keys.add(key)
                meta["legacy_fill_count"] += 1
                if len(existing) >= _MAX_PER_PATHWAY:
                    break

    meta["matched_intervention_count"] = len(
        {n for names in result.values() for n in names}
    )
    meta["best_hits"] = {
        h.name: {
            "entity_id": h.entity_id,
            "pathway_code": h.pathway_code,
            "confidence": h.confidence,
            "evidence_type": h.evidence_type,
            "citation": h.citation,
        }
        for h in list(best_hit_by_name.values())[:40]
    }
    return result, meta


def graph_hits_to_evidence_snippets(
    hits_by_name: dict[str, GraphInterventionHit] | None,
    pathway_to_interventions: dict[str, list[str]],
) -> list[EvidenceSnippet]:
    """Convert graph modulation hits into Stage-4 evidence snippets."""
    if not hits_by_name:
        # Rebuild from pathway map names without rich hits
        return []

    snippets: list[EvidenceSnippet] = []
    seen: set[str] = set()
    for names in pathway_to_interventions.values():
        for name in names:
            hit = hits_by_name.get(normalize_name(name)) or hits_by_name.get(name)
            if hit is None:
                # try case-insensitive scan
                hit = next(
                    (h for k, h in hits_by_name.items() if normalize_name(k) == normalize_name(name)),
                    None,
                )
            if hit is None:
                continue
            key = f"{hit.name}:{hit.citation or hit.entity_id}"
            if key in seen:
                continue
            seen.add(key)
            quality = min(0.92, max(0.2, hit.confidence))
            if hit.evidence_type == GraphEvidenceType.PREDICTED.value:
                quality = min(quality, 0.4)
                study_type = StudyType.PRECLINICAL
            elif hit.evidence_type == GraphEvidenceType.META_ANALYTIC.value:
                study_type = StudyType.META_ANALYSIS
            elif hit.evidence_type == GraphEvidenceType.CLINICAL_HUMAN.value:
                study_type = StudyType.RCT
            else:
                study_type = StudyType.MECHANISTIC

            external_id = hit.citation or f"graph:{hit.entity_id}"
            url = None
            if hit.citation and hit.citation.upper().startswith("PMID:"):
                pmid = hit.citation.split(":", 1)[-1]
                url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

            snippets.append(
                EvidenceSnippet(
                    source=StudySource.PUBMED if url else StudySource.PUBMED,
                    external_id=external_id,
                    title=hit.notes or f"Graph {hit.relationship}: {hit.name} ↔ {hit.pathway_code}",
                    year=None,
                    study_type=study_type,
                    quality_score=quality,
                    url=url,
                    abstract_snippet=hit.notes,
                    intervention_name=hit.name,
                )
            )
    return snippets


def collect_best_hits(
    session: Session,
    pathway_activations: list[PathwayActivation],
) -> dict[str, GraphInterventionHit]:
    pathway_codes = {a.pathway_code for a in pathway_activations}
    hits = _load_modulation_hits(session, pathway_codes)
    best: dict[str, GraphInterventionHit] = {}
    for hit in hits:
        key = normalize_name(hit.name)
        prev = best.get(key)
        if prev is None or _rank_hit(hit) < _rank_hit(prev):
            best[key] = hit
    return best
