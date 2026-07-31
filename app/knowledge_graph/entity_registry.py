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

    all_synonyms = [canonical_name, display_name or canonical_name, *(synonyms or [])]
    seen_normalized: set[str] = set()
    for synonym in all_synonyms:
        cleaned = (synonym or "").strip()
        if not cleaned:
            continue
        normalized = normalize_entity_name(cleaned)
        if not normalized or normalized in seen_normalized:
            continue
        seen_normalized.add(normalized)
        db.add(
            EntitySynonym(
                entity_id_fk=entity.id,
                synonym=cleaned,
                synonym_normalized=normalized,
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


async def _bootstrap_seq_counters(db: AsyncSession) -> dict[CanonicalEntityType, int]:
    counters: dict[CanonicalEntityType, int] = {}
    for entity_type, prefix in ENTITY_ID_PREFIX.items():
        result = await db.execute(
            select(func.max(CanonicalEntity.entity_id)).where(CanonicalEntity.entity_id.like(f"{prefix}-%"))
        )
        current_max = result.scalar()
        if not current_max:
            counters[entity_type] = 0
            continue
        try:
            counters[entity_type] = int(current_max.rsplit("-", 1)[-1])
        except ValueError:
            counters[entity_type] = 0
    return counters


def _next_bootstrap_entity_id(
    counters: dict[CanonicalEntityType, int], entity_type: CanonicalEntityType
) -> str:
    counters[entity_type] = counters.get(entity_type, 0) + 1
    return f"{ENTITY_ID_PREFIX[entity_type]}-{counters[entity_type]:06d}"


async def _bootstrap_register_entity(
    db: AsyncSession,
    *,
    canonical_name: str,
    display_name: str,
    entity_type: CanonicalEntityType,
    counters: dict[CanonicalEntityType, int],
    coverage_tier: CoverageTier,
    review_status: EntityReviewStatus,
    intervention_id: uuid.UUID | None = None,
    compound_id: uuid.UUID | None = None,
    external_ids: list[tuple[ExternalIdSource, str]] | None = None,
    notes: str | None = None,
) -> CanonicalEntity:
    entity = CanonicalEntity(
        entity_id=_next_bootstrap_entity_id(counters, entity_type),
        canonical_name=canonical_name.strip(),
        display_name=display_name.strip(),
        entity_type=entity_type.value,
        coverage_tier=coverage_tier.value,
        review_status=review_status.value,
        intervention_id=intervention_id,
        compound_id=compound_id,
        notes=notes,
    )
    db.add(entity)
    await db.flush()
    db.add(
        EntitySynonym(
            entity_id_fk=entity.id,
            synonym=canonical_name.strip(),
            synonym_normalized=normalize_entity_name(canonical_name),
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

    existing_entities = list((await db.execute(select(CanonicalEntity))).scalars().all())
    by_intervention_id = {
        entity.intervention_id: entity for entity in existing_entities if entity.intervention_id
    }
    by_compound_id = {entity.compound_id: entity for entity in existing_entities if entity.compound_id}
    by_name_type = {
        (normalize_entity_name(entity.canonical_name), entity.entity_type): entity for entity in existing_entities
    }

    existing_edges = set(
        (
            row.source_entity_id,
            row.target_entity_id,
            row.relationship_type,
        )
        for row in (await db.execute(select(GraphEdge))).scalars().all()
    )

    counters = await _bootstrap_seq_counters(db)
    intervention_entities: dict[uuid.UUID, CanonicalEntity] = {}

    _CHUNK = 100
    interventions = list((await db.execute(select(Intervention))).scalars().all())
    pending_flush = 0
    for intervention in interventions:
        stats["interventions_total"] += 1
        entity_type = intervention_category_to_entity_type(intervention.category)
        existing = by_intervention_id.get(intervention.id) or by_name_type.get(
            (normalize_entity_name(intervention.name), entity_type.value)
        )

        if existing is not None:
            stats["entities_skipped"] += 1
            if existing.intervention_id is None:
                existing.intervention_id = intervention.id
                by_intervention_id[intervention.id] = existing
            intervention_entities[intervention.id] = existing
            continue

        entity = await _bootstrap_register_entity(
            db,
            canonical_name=intervention.name,
            display_name=intervention.name,
            entity_type=entity_type,
            counters=counters,
            coverage_tier=coverage_tier,
            review_status=review_status,
            intervention_id=intervention.id,
            external_ids=[(ExternalIdSource.INTERVENTION, str(intervention.id))],
            notes="Bootstrapped from interventions table",
        )
        stats["entities_created"] += 1
        by_intervention_id[intervention.id] = entity
        by_name_type[(normalize_entity_name(intervention.name), entity_type.value)] = entity
        intervention_entities[intervention.id] = entity
        pending_flush += 1
        if pending_flush >= _CHUNK:
            await db.flush()
            await db.commit()
            counters = await _bootstrap_seq_counters(db)
            pending_flush = 0

    if pending_flush:
        await db.flush()
        await db.commit()
        counters = await _bootstrap_seq_counters(db)

    compound_entities: dict[uuid.UUID, CanonicalEntity] = {}
    compounds = list((await db.execute(select(Compound))).scalars().all())
    pending_flush = 0
    for compound in compounds:
        existing = by_compound_id.get(compound.id) or by_name_type.get(
            (normalize_entity_name(compound.name), CanonicalEntityType.COMPOUND.value)
        )
        if existing is None:
            entity = await _bootstrap_register_entity(
                db,
                canonical_name=compound.name,
                display_name=compound.name,
                entity_type=CanonicalEntityType.COMPOUND,
                counters=counters,
                coverage_tier=coverage_tier,
                review_status=review_status,
                compound_id=compound.id,
                external_ids=[(ExternalIdSource.COMPOUND, str(compound.id))],
                notes="Bootstrapped from compounds table",
            )
            stats["compounds_created"] += 1
            by_compound_id[compound.id] = entity
            by_name_type[(normalize_entity_name(compound.name), CanonicalEntityType.COMPOUND.value)] = entity
            compound_entities[compound.id] = entity
            pending_flush += 1
            if pending_flush >= _CHUNK:
                await db.flush()
                await db.commit()
                counters = await _bootstrap_seq_counters(db)
                pending_flush = 0
        else:
            compound_entities[compound.id] = existing
            if existing.compound_id is None:
                existing.compound_id = compound.id

    if pending_flush:
        await db.flush()
        await db.commit()
        counters = await _bootstrap_seq_counters(db)

    intervention_entity_ids = {
        entity.intervention_id: entity.id
        for entity in (
            await db.execute(select(CanonicalEntity).where(CanonicalEntity.intervention_id.isnot(None)))
        ).scalars()
    }
    compound_entity_ids = {
        entity.compound_id: entity.id
        for entity in (
            await db.execute(select(CanonicalEntity).where(CanonicalEntity.compound_id.isnot(None)))
        ).scalars()
    }

    def _add_edge(source_id: uuid.UUID, target_id: uuid.UUID, notes: str) -> None:
        key = (source_id, target_id, GraphRelationshipType.CONTAINS.value)
        if key in existing_edges:
            return
        db.add(
            GraphEdge(
                source_entity_id=source_id,
                target_entity_id=target_id,
                relationship_type=GraphRelationshipType.CONTAINS.value,
                evidence_type=GraphEvidenceType.MECHANISTIC.value,
                confidence=0.85,
                review_status=EntityReviewStatus.PRODUCTION_APPROVED.value,
                source_provenance="bootstrap_interventions",
                notes=notes,
            )
        )
        existing_edges.add(key)
        stats["composition_edges_created"] += 1

    for link in (await db.execute(select(InterventionCompound))).scalars().all():
        source_id = intervention_entity_ids.get(link.intervention_id)
        target_id = compound_entity_ids.get(link.compound_id)
        if source_id is None or target_id is None:
            continue
        _add_edge(
            source_id,
            target_id,
            f"From intervention_compounds ({link.role or 'constituent'})",
        )

    for link in (await db.execute(select(FoodCompoundSource))).scalars().all():
        food_id = intervention_entity_ids.get(link.food_intervention_id)
        compound_id = intervention_entity_ids.get(link.compound_intervention_id)
        if food_id is None or compound_id is None:
            continue
        note = f"From food_compound_sources ({link.richness.value})"
        if link.typical_serving:
            note += f"; serving: {link.typical_serving}"
        _add_edge(food_id, compound_id, note)

    await db.flush()
    await db.commit()
    return stats