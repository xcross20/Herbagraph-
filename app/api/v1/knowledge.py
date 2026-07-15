"""Canonical intervention registry and enrichment pipeline APIs."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_admin_user, get_current_user, get_db
from app.knowledge_graph.enrichment_worker import enqueue_enrichment, run_enrichment_batch
from app.knowledge_graph.entity_registry import bootstrap_from_interventions, register_entity, resolve_entity_by_name
from app.models.canonical_entity import CanonicalEntity, EnrichmentQueueItem
from app.models.enums import CoverageTier, EnrichmentQueueStatus, EntityReviewStatus
from app.models.user import User
from app.schemas.knowledge import (
    CanonicalEntityCreate,
    CanonicalEntityRead,
    EnrichmentEnqueueRequest,
    EnrichmentQueueItemRead,
    KnowledgeCoverageSummary,
)

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


def _entity_to_read(entity: CanonicalEntity) -> CanonicalEntityRead:
    return CanonicalEntityRead.model_validate(entity)


@router.get("/coverage", response_model=KnowledgeCoverageSummary)
async def knowledge_coverage(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeCoverageSummary:
    total = (await db.execute(select(func.count()).select_from(CanonicalEntity))).scalar() or 0
    tier_a = (
        await db.execute(
            select(func.count()).select_from(CanonicalEntity).where(CanonicalEntity.coverage_tier == CoverageTier.TIER_A.value)
        )
    ).scalar() or 0
    tier_b = (
        await db.execute(
            select(func.count()).select_from(CanonicalEntity).where(CanonicalEntity.coverage_tier == CoverageTier.TIER_B.value)
        )
    ).scalar() or 0
    tier_c = (
        await db.execute(
            select(func.count()).select_from(CanonicalEntity).where(CanonicalEntity.coverage_tier == CoverageTier.TIER_C.value)
        )
    ).scalar() or 0
    production = (
        await db.execute(
            select(func.count())
            .select_from(CanonicalEntity)
            .where(CanonicalEntity.review_status == EntityReviewStatus.PRODUCTION_APPROVED.value)
        )
    ).scalar() or 0
    pending_queue = (
        await db.execute(
            select(func.count())
            .select_from(EnrichmentQueueItem)
            .where(EnrichmentQueueItem.status == EnrichmentQueueStatus.PENDING.value)
        )
    ).scalar() or 0

    evidence_label = "High" if production >= 50 else "Moderate" if production >= 10 else "Developing"
    entity_label = "High" if total >= 500 else "Moderate" if total >= 100 else "Limited"

    return KnowledgeCoverageSummary(
        entity_count=total,
        tier_a_count=tier_a,
        tier_b_count=tier_b,
        tier_c_count=tier_c,
        production_approved_count=production,
        pending_enrichment_count=pending_queue,
        evidence_coverage_label=evidence_label,
        entity_coverage_label=entity_label,
        last_evidence_review=datetime.now(timezone.utc).strftime("%B %Y"),
    )


@router.get("/entities", response_model=list[CanonicalEntityRead])
async def list_entities(
    search: str | None = None,
    entity_type: str | None = None,
    coverage_tier: CoverageTier | None = None,
    limit: int = Query(default=50, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CanonicalEntityRead]:
    query = select(CanonicalEntity).options(
        selectinload(CanonicalEntity.synonyms),
        selectinload(CanonicalEntity.external_ids),
    )
    if search:
        query = query.where(
            CanonicalEntity.canonical_name.ilike(f"%{search}%")
            | CanonicalEntity.display_name.ilike(f"%{search}%")
        )
    if entity_type:
        query = query.where(CanonicalEntity.entity_type == entity_type)
    if coverage_tier is not None:
        query = query.where(CanonicalEntity.coverage_tier == coverage_tier.value)
    query = query.order_by(CanonicalEntity.canonical_name).limit(limit)
    result = await db.execute(query)
    return [_entity_to_read(entity) for entity in result.scalars().all()]


@router.get("/entities/resolve/{name}", response_model=CanonicalEntityRead | None)
async def resolve_entity(
    name: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CanonicalEntityRead | None:
    entity = await resolve_entity_by_name(db, name)
    if entity is None:
        return None
    result = await db.execute(
        select(CanonicalEntity)
        .options(
            selectinload(CanonicalEntity.synonyms),
            selectinload(CanonicalEntity.external_ids),
        )
        .where(CanonicalEntity.id == entity.id)
    )
    loaded = result.scalar_one()
    return _entity_to_read(loaded)


@router.get("/entities/{entity_uuid}", response_model=CanonicalEntityRead)
async def get_entity(
    entity_uuid: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CanonicalEntityRead:
    result = await db.execute(
        select(CanonicalEntity)
        .options(
            selectinload(CanonicalEntity.synonyms),
            selectinload(CanonicalEntity.external_ids),
        )
        .where(CanonicalEntity.id == entity_uuid)
    )
    entity = result.scalar_one_or_none()
    if entity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found")
    return _entity_to_read(entity)


@router.post("/entities", response_model=CanonicalEntityRead, status_code=status.HTTP_201_CREATED)
async def create_entity(
    payload: CanonicalEntityCreate,
    _: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> CanonicalEntityRead:
    entity = await register_entity(
        db,
        canonical_name=payload.canonical_name,
        display_name=payload.display_name,
        entity_type=payload.entity_type,
        subtype=payload.subtype,
        species=payload.species,
        plant_part=payload.plant_part,
        preparation=payload.preparation,
        synonyms=payload.synonyms,
        coverage_tier=payload.coverage_tier,
        review_status=payload.review_status,
    )
    await db.commit()
    await db.refresh(entity, attribute_names=["synonyms", "external_ids"])
    return _entity_to_read(entity)


@router.get("/enrichment/queue", response_model=list[EnrichmentQueueItemRead])
async def list_enrichment_queue(
    status_filter: EnrichmentQueueStatus | None = None,
    limit: int = Query(default=50, le=200),
    _: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> list[EnrichmentQueueItemRead]:
    query = select(EnrichmentQueueItem).order_by(
        EnrichmentQueueItem.priority.asc(), EnrichmentQueueItem.created_at.asc()
    )
    if status_filter is not None:
        query = query.where(EnrichmentQueueItem.status == status_filter.value)
    query = query.limit(limit)
    result = await db.execute(query)
    return [EnrichmentQueueItemRead.model_validate(item) for item in result.scalars().all()]


@router.post("/enrichment/queue", response_model=EnrichmentQueueItemRead, status_code=status.HTTP_201_CREATED)
async def enqueue_entity_enrichment(
    payload: EnrichmentEnqueueRequest,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> EnrichmentQueueItemRead:
    item = await enqueue_enrichment(
        db,
        query_name=payload.query_name,
        priority=payload.priority,
        requested_by=admin.email,
    )
    await db.commit()
    await db.refresh(item)
    return EnrichmentQueueItemRead.model_validate(item)


@router.post("/enrichment/run", response_model=list[EnrichmentQueueItemRead])
async def run_enrichment_worker(
    limit: int = Query(default=5, le=20),
    _: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> list[EnrichmentQueueItemRead]:
    processed = await run_enrichment_batch(db, limit=limit)
    return [EnrichmentQueueItemRead.model_validate(item) for item in processed]


@router.post("/bootstrap/interventions", response_model=dict[str, int])
async def bootstrap_intervention_registry(
    _: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    created = await bootstrap_from_interventions(db)
    return {"entities_registered": created}