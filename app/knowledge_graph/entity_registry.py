"""Canonical intervention registry — entity creation, lookup, and ID assignment."""

from __future__ import annotations

import re
import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.canonical_entity import ENTITY_ID_PREFIX, CanonicalEntity, EntityExternalId, EntitySynonym
from app.models.enums import (
    CanonicalEntitySubtype,
    CanonicalEntityType,
    CoverageTier,
    EntityReviewStatus,
    ExternalIdSource,
    InterventionCategory,
)
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


async def bootstrap_from_interventions(
    db: AsyncSession,
    *,
    coverage_tier: CoverageTier = CoverageTier.TIER_A,
    review_status: EntityReviewStatus = EntityReviewStatus.PRODUCTION_APPROVED,
) -> int:
    """Seed canonical registry from existing curated interventions (Tier A core)."""
    result = await db.execute(select(Intervention))
    interventions = list(result.scalars().all())
    created = 0
    for intervention in interventions:
        entity_type = intervention_category_to_entity_type(intervention.category)
        before_id = intervention.id
        existing = await resolve_entity_by_name(db, intervention.name, entity_type=entity_type)
        if existing is not None:
            continue
        await register_entity(
            db,
            canonical_name=intervention.name,
            display_name=intervention.name,
            entity_type=entity_type,
            coverage_tier=coverage_tier,
            review_status=review_status,
            intervention_id=before_id,
            external_ids=[(ExternalIdSource.INTERVENTION, str(before_id))],
            notes="Bootstrapped from interventions table",
        )
        created += 1
    await db.commit()
    return created