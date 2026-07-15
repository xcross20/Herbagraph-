"""Canonical intervention registry — entity creation, lookup, and ID assignment."""

from __future__ import annotations

import re
import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.canonical_entity import (
    ENTITY_ID_PREFIX,
    CanonicalEntity,
    EntityExternalId,
    EntitySynonym,
    GraphEdge,
)
from app.models.compound import Compound, InterventionCompound
from app.models.enums import (
    CanonicalEntitySubtype,
    CanonicalEntityType,
    CoverageTier,
    EntityReviewStatus,
    ExternalIdSource,
    GraphEvidenceType,
    GraphRelationshipType,
    InterventionCategory,
)
from app.models.food_compound_source import FoodCompoundSource
from app.models.intervention import Intervention

_NORMALIZE_RE = re.compile(r"[^a-z0-9]+")


def normalize_entity_name(name: str) -> str:
    return _NORMALIZE_RE.sub(" ", name.strip().lower()).strip()


def intervention_category_to_entity_type(category: InterventionCategory) -> CanonicalEntityType:
    mapping = {
        InterventionCategory.FOOD: CanonicalEntityType.FOOD,
        InterventionCategory.HERB: CanonicalEntityType.BOTANICAL,
        InterventionCategory.PHYTOCHEMICAL: CanonicalEntityType.COMPOUND,
        InterventionCategory.SUPPLEMENT: CanonicalEntityType.SUPPLEMENT,
        InterventionCategory.MEDICATION: CanonicalEntityType.MEDICATION,
        InterventionCategory.PEPTIDE: CanonicalEntityType.PEPTIDE,
        InterventionCategory.EXERCISE: CanonicalEntityType.LIFESTYLE,
        InterventionCategory.SLEEP: CanonicalEntityType.LIFESTYLE,
        InterventionCategory.STRESS_REDUCTION: CanonicalEntityType.LIFESTYLE,
        InterventionCategory.BEHAVIOR: CanonicalEntityType.LIFESTYLE,
        InterventionCategory.ENVIRONMENTAL: CanonicalEntityType.LIFESTYLE,
        InterventionCategory.HORMONE: CanonicalEntityType.SUPPLEMENT,
    }
    return mapping.get(category, CanonicalEntityType.SUPPLEMENT)


async def _next_entity_id(db: AsyncSession, entity_type: CanonicalEntityType) -> str:
    prefix = ENTITY_ID_PREFIX[entity_type]
    pattern = f"{prefix}-%"
    result = await db.execute(
        select(func.max(CanonicalEntity.entity_id)).where(CanonicalEntity.entity_id.like(pattern))
    )
    current_max = result.scalar()
    if not current_max:
        return f"{prefix}-000001"
    try:
        seq = int(current_max.rsplit("-", 1)[-1])
    except ValueError:
        seq = 0
    return f"{prefix}-{seq + 1:06d}"


async def resolve_entity_by_name(
    db: AsyncSession,
    name: str,
    *,
    entity_type: CanonicalEntityType | None = None,
) -> CanonicalEntity | None:
    """Level 2 synonym resolution — match canonical name or any alias."""
    normalized = normalize_entity_name(name)
    if not normalized:
        return None

    query = (
        select(CanonicalEntity)
        .outerjoin(EntitySynonym, EntitySynonym.entity_id_fk == CanonicalEntity.id)
        .where(
            or_(
                func.lower(CanonicalEntity.canonical_name) == normalized,
                func.lower(CanonicalEntity.display_name) == normalized,
                EntitySynonym.synonym_normalized == normalized,
            )
        )
        .limit(1)
    )
    if entity_type is not None:
        query = query.where(CanonicalEntity.entity_type == entity_type.value)
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def register_entity(
    db: AsyncSession,
    *,
    canonical_name: str,
    display_name: str | None = None,
    entity_type: CanonicalEntityType,
    subtype: CanonicalEntitySubtype | None = None,
    species: str | None = None,
    plant_part: str | None = None,
    preparation: str | None = None,
    synonyms: list[str] | None = None,
    coverage_tier: CoverageTier = CoverageTier.TIER_C,
    review_status: EntityReviewStatus = EntityReviewStatus.MACHINE_GENERATED,
    intervention_id: uuid.UUID | None = None,
    compound_id: uuid.UUID | None = None,
    external_ids: list[tuple[ExternalIdSource, str]] | None = None,
    notes: str | None = None,
) -> CanonicalEntity:
    existing = await resolve_entity_by_name(db, canonical_name, entity_type=entity_type)
    if existing is not None:
        return existing

    entity = CanonicalEntity(
        entity_id=await _next_entity_id(db, entity_type),
        canonical_name=canonical_name.strip(),
        display_name=(display_name or canonical_name).strip(),
        entity_type=entity_type.value,
        subtype=subtype.value if subtype else None,
        species=species,
        plant_part=plant_part,
        preparation=preparation,
        coverage_tier=coverage_tier.value,
        review_status=review_status.value,
        intervention_id=intervention_id,
        compound_id=compound_id,
        notes=notes,
    )
    db.add(entity)
    await db.flush()

    all_synonyms = {canonical_name, display_name or canonical_name, *(synonyms or [])}
    for synonym in all_synonyms:
        cleaned = synonym.strip()
        if not cleaned:
            continue
        db.add(
            EntitySynonym(
                entity_id_fk=entity.id,
                synonym=cleaned,
                synonym_normalized=normalize_entity_name(cleaned),
            )
        )

    for source, ext_id in external_ids or []:
        db.add(
            EntityExternalId(
                entity_id_fk=entity.id,
                source=source.value,
                external_id=ext_id,
            )
        )

    return entity


async def _entity_for_intervention_id(
    db: AsyncSession, intervention_id: uuid.UUID
) -> CanonicalEntity | None:
    result = await db.execute(
        select(CanonicalEntity).where(CanonicalEntity.intervention_id == intervention_id).limit(1)
    )
    return result.scalar_one_or_none()


async def _ensure_composition_edge(
    db: AsyncSession,
    *,
    source_entity_id: uuid.UUID,
    target_entity_id: uuid.UUID,
    notes: str,
) -> bool:
    existing = await db.execute(
        select(GraphEdge.id)
        .where(
            GraphEdge.source_entity_id == source_entity_id,
            GraphEdge.target_entity_id == target_entity_id,
            GraphEdge.relationship_type == GraphRelationshipType.CONTAINS.value,
        )
        .limit(1)
    )
    if existing.scalar_one_or_none() is not None:
        return False
    db.add(
        GraphEdge(
            source_entity_id=source_entity_id,
            target_entity_id=target_entity_id,
            relationship_type=GraphRelationshipType.CONTAINS.value,
            evidence_type=GraphEvidenceType.MECHANISTIC.value,
            confidence=0.85,
            review_status=EntityReviewStatus.PRODUCTION_APPROVED.value,
            source_provenance="bootstrap_interventions",
            notes=notes,
        )
    )
    return True


async def bootstrap_from_interventions(
    db: AsyncSession,
    *,
    coverage_tier: CoverageTier = CoverageTier.TIER_A,
    review_status: EntityReviewStatus = EntityReviewStatus.PRODUCTION_APPROVED,
) -> dict[str, int]:
    """Seed canonical registry from the curated interventions catalog (Tier A core).

    Idempotent: skips entities and composition edges that already exist.
    """
    stats = {
        "interventions_total": 0,
        "entities_created": 0,
        "entities_skipped": 0,
        "compounds_created": 0,
        "composition_edges_created": 0,
    }

    intervention_entities: dict[uuid.UUID, CanonicalEntity] = {}

    interventions = list((await db.execute(select(Intervention))).scalars().all())
    for intervention in interventions:
        stats["interventions_total"] += 1
        entity_type = intervention_category_to_entity_type(intervention.category)
        existing = await _entity_for_intervention_id(db, intervention.id)
        if existing is None:
            existing = await resolve_entity_by_name(db, intervention.name, entity_type=entity_type)

        if existing is not None:
            stats["entities_skipped"] += 1
            if existing.intervention_id is None:
                existing.intervention_id = intervention.id
            intervention_entities[intervention.id] = existing
            continue

        entity = await register_entity(
            db,
            canonical_name=intervention.name,
            display_name=intervention.name,
            entity_type=entity_type,
            coverage_tier=coverage_tier,
            review_status=review_status,
            intervention_id=intervention.id,
            external_ids=[(ExternalIdSource.INTERVENTION, str(intervention.id))],
            notes="Bootstrapped from interventions table",
        )
        stats["entities_created"] += 1
        intervention_entities[intervention.id] = entity

    await db.flush()

    compound_entities: dict[uuid.UUID, CanonicalEntity] = {}
    compounds = list((await db.execute(select(Compound))).scalars().all())
    for compound in compounds:
        existing = await resolve_entity_by_name(db, compound.name, entity_type=CanonicalEntityType.COMPOUND)
        if existing is None:
            entity = await register_entity(
                db,
                canonical_name=compound.name,
                display_name=compound.name,
                entity_type=CanonicalEntityType.COMPOUND,
                coverage_tier=coverage_tier,
                review_status=review_status,
                compound_id=compound.id,
                external_ids=[(ExternalIdSource.COMPOUND, str(compound.id))],
                notes="Bootstrapped from compounds table",
            )
            stats["compounds_created"] += 1
            compound_entities[compound.id] = entity
        else:
            compound_entities[compound.id] = existing

    await db.flush()

    intervention_compounds = list((await db.execute(select(InterventionCompound))).scalars().all())
    for link in intervention_compounds:
        source = intervention_entities.get(link.intervention_id)
        target = compound_entities.get(link.compound_id)
        if source is None or target is None:
            continue
        if await _ensure_composition_edge(
            db,
            source_entity_id=source.id,
            target_entity_id=target.id,
            notes=f"From intervention_compounds ({link.role or 'constituent'})",
        ):
            stats["composition_edges_created"] += 1

    food_links = list((await db.execute(select(FoodCompoundSource))).scalars().all())
    for link in food_links:
        food_entity = intervention_entities.get(link.food_intervention_id)
        compound_entity = intervention_entities.get(link.compound_intervention_id)
        if food_entity is None or compound_entity is None:
            continue
        note = f"From food_compound_sources ({link.richness.value})"
        if link.typical_serving:
            note += f"; serving: {link.typical_serving}"
        if await _ensure_composition_edge(
            db,
            source_entity_id=food_entity.id,
            target_entity_id=compound_entity.id,
            notes=note,
        ):
            stats["composition_edges_created"] += 1

    await db.commit()
    return stats