"""Canonical graph knowledge path — intervention selection via registry + composition.

When knowledge_path=canonical, Stage 4 filters the routed intervention set to entities
that exist in canonical_entities (preferring Tier A / production-approved). Composition
edges (CONTAINS) supply whole-food sources. If the registry is empty, returns an empty
mapping so the operator knows to run bootstrap_canonical_registry.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.canonical_entity import CanonicalEntity, GraphEdge
from app.models.enums import CoverageTier, EntityReviewStatus, GraphRelationshipType
from app.pipeline.intervention_catalog import build_interventions_for_routing
from app.pipeline.test_type_router import RecommendationRoutingContext
from app.schemas.pipeline import NormalizedLabResult, PathwayActivation

_NORMALIZE_RE = re.compile(r"[^a-z0-9]+")


def normalize_name(name: str) -> str:
    return _NORMALIZE_RE.sub(" ", name.strip().lower()).strip()


@dataclass
class RegistryEntity:
    id: object
    entity_id: str
    canonical_name: str
    display_name: str
    entity_type: str
    coverage_tier: str
    review_status: str


@dataclass
class CanonicalRegistryIndex:
    by_name: dict[str, RegistryEntity] = field(default_factory=dict)
    entity_count: int = 0
    production_count: int = 0

    def resolve(self, name: str) -> RegistryEntity | None:
        return self.by_name.get(normalize_name(name))


def load_registry_index(session: Session) -> CanonicalRegistryIndex:
    """Load canonical entities into an in-memory name index (sync session)."""
    rows = list(session.execute(select(CanonicalEntity)).scalars().all())
    index = CanonicalRegistryIndex(entity_count=len(rows))
    for row in rows:
        entity = RegistryEntity(
            id=row.id,
            entity_id=row.entity_id,
            canonical_name=row.canonical_name,
            display_name=row.display_name or row.canonical_name,
            entity_type=row.entity_type,
            coverage_tier=row.coverage_tier,
            review_status=row.review_status,
        )
        if entity.review_status == EntityReviewStatus.PRODUCTION_APPROVED.value:
            index.production_count += 1
        for key in {
            normalize_name(entity.canonical_name),
            normalize_name(entity.display_name),
        }:
            if not key:
                continue
            existing = index.by_name.get(key)
            if existing is None or _prefer_entity(entity, existing):
                index.by_name[key] = entity
    return index


def _prefer_entity(candidate: RegistryEntity, current: RegistryEntity) -> bool:
    """Prefer production-approved / Tier A when duplicate names exist."""
    tier_rank = {
        CoverageTier.TIER_A.value: 0,
        CoverageTier.TIER_B.value: 1,
        CoverageTier.TIER_C.value: 2,
    }
    review_rank = {
        EntityReviewStatus.PRODUCTION_APPROVED.value: 0,
        EntityReviewStatus.HUMAN_REVIEWED.value: 1,
        EntityReviewStatus.MACHINE_VERIFIED.value: 2,
        EntityReviewStatus.MACHINE_GENERATED.value: 3,
        EntityReviewStatus.DEPRECATED.value: 9,
    }
    c_score = (
        review_rank.get(candidate.review_status, 5),
        tier_rank.get(candidate.coverage_tier, 5),
    )
    e_score = (
        review_rank.get(current.review_status, 5),
        tier_rank.get(current.coverage_tier, 5),
    )
    return c_score < e_score


def build_interventions_for_canonical_path(
    routing: RecommendationRoutingContext,
    pathway_activations: list[PathwayActivation],
    normalized_labs: list[NormalizedLabResult],
    session: Session,
) -> tuple[dict[str, list[str]], dict]:
    """Route interventions then keep only names present in the canonical registry."""
    legacy_map = build_interventions_for_routing(routing, pathway_activations, normalized_labs)
    index = load_registry_index(session)
    meta: dict = {
        "knowledge_path": "canonical",
        "registry_entity_count": index.entity_count,
        "registry_production_count": index.production_count,
        "legacy_intervention_count": sum(len(v) for v in legacy_map.values()),
        "matched_intervention_count": 0,
        "unmatched_interventions": [],
        "registry_empty": index.entity_count == 0,
    }

    if index.entity_count == 0:
        return {}, meta

    filtered: dict[str, list[str]] = {}
    unmatched: list[str] = []
    seen_matched: set[str] = set()

    for pathway_code, names in legacy_map.items():
        kept: list[str] = []
        for name in names:
            entity = index.resolve(name)
            if entity is None:
                if name not in unmatched:
                    unmatched.append(name)
                continue
            display = entity.display_name
            if display not in kept:
                kept.append(display)
            seen_matched.add(display)
        if kept:
            filtered[pathway_code] = kept

    meta["matched_intervention_count"] = len(seen_matched)
    meta["unmatched_interventions"] = unmatched[:40]
    return filtered, meta


def composition_food_sources(
    session: Session,
    intervention_name: str,
    *,
    limit: int = 8,
) -> list[dict]:
    """Return CONTAINS targets for a food/botanical entity as food-source style dicts."""
    index = load_registry_index(session)
    entity = index.resolve(intervention_name)
    if entity is None:
        return []

    edges = list(
        session.execute(
            select(GraphEdge).where(
                GraphEdge.source_entity_id == entity.id,
                GraphEdge.relationship_type == GraphRelationshipType.CONTAINS.value,
            )
        ).scalars().all()
    )
    if not edges:
        return []

    target_ids = [e.target_entity_id for e in edges]
    targets = {
        t.id: t
        for t in session.execute(
            select(CanonicalEntity).where(CanonicalEntity.id.in_(target_ids))
        ).scalars().all()
    }
    results: list[dict] = []
    for edge in edges[:limit]:
        target = targets.get(edge.target_entity_id)
        if target is None:
            continue
        results.append(
            {
                "food_name": target.display_name or target.canonical_name,
                "richness": "moderate",
                "typical_serving": None,
                "entity_id": target.entity_id,
                "source": "canonical_graph",
            }
        )
    return results
