"""Automated expansion worker — candidate graph curation pipeline."""

from __future__ import annotations

import logging

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.chebi import lookup_chebi_id
from app.integrations.pubchem import get_compound_cid, get_compound_properties
from app.integrations.usda_fooddata import search_food
from app.knowledge_graph.entity_registry import normalize_entity_name, register_entity, resolve_entity_by_name
from app.models.canonical_entity import EnrichmentQueueItem, EntityExternalId, GraphEdge
from app.models.enums import (
    CanonicalEntityType,
    CoverageTier,
    EnrichmentQueueStatus,
    EntityReviewStatus,
    ExternalIdSource,
    GraphEvidenceType,
    GraphRelationshipType,
)

logger = logging.getLogger(__name__)

ENRICHMENT_STEPS = (
    "verify_not_duplicate",
    "resolve_synonyms",
    "classify_entity_type",
    "identify_constituents",
    "retrieve_external_ids",
    "generate_candidate_edges",
    "flag_for_review",
)


async def enqueue_enrichment(
    db: AsyncSession,
    *,
    query_name: str,
    priority: int = 100,
    requested_by: str | None = None,
) -> EnrichmentQueueItem:
    normalized = normalize_entity_name(query_name)
    existing_queue = await db.execute(
        select(EnrichmentQueueItem)
        .where(
            EnrichmentQueueItem.query_normalized == normalized,
            EnrichmentQueueItem.status.in_(
                [EnrichmentQueueStatus.PENDING.value, EnrichmentQueueStatus.IN_PROGRESS.value]
            ),
        )
        .limit(1)
    )
    queued = existing_queue.scalar_one_or_none()
    if queued is not None:
        return queued

    item = EnrichmentQueueItem(
        query_name=query_name.strip(),
        query_normalized=normalized,
        status=EnrichmentQueueStatus.PENDING.value,
        priority=priority,
        requested_by=requested_by,
    )
    db.add(item)
    await db.flush()
    return item


async def _infer_entity_type(query_name: str) -> CanonicalEntityType:
    lowered = query_name.lower()
    if any(token in lowered for token in ("extract", "supplement", "capsule", "tablet")):
        return CanonicalEntityType.SUPPLEMENT
    if any(token in lowered for token in ("acid", "flavonoid", "polyphenol", "curcumin", "quercetin")):
        return CanonicalEntityType.COMPOUND
    if any(token in lowered for token in ("tea", "root", "bark", "herb", "ginseng", "turmeric")):
        return CanonicalEntityType.BOTANICAL
    return CanonicalEntityType.FOOD


async def _attach_external_ids(
    db: AsyncSession,
    entity,
    query_name: str,
    entity_type: CanonicalEntityType,
    client: httpx.AsyncClient,
) -> list[str]:
    attached: list[str] = []
    if entity_type in (CanonicalEntityType.COMPOUND, CanonicalEntityType.NUTRIENT, CanonicalEntityType.SUPPLEMENT):
        cid = await get_compound_cid(query_name, client)
        if cid is not None:
            db.add(
                EntityExternalId(
                    entity_id_fk=entity.id,
                    source=ExternalIdSource.PUBCHEM.value,
                    external_id=str(cid),
                )
            )
            attached.append(f"pubchem:{cid}")
            props = await get_compound_properties(cid, client)
            if props:
                entity.notes = (entity.notes or "") + f"\nPubChem: {props.get('IUPACName', '')}".strip()

        chebi = await lookup_chebi_id(query_name, client)
        if chebi:
            db.add(
                EntityExternalId(
                    entity_id_fk=entity.id,
                    source=ExternalIdSource.CHEBI.value,
                    external_id=chebi,
                )
            )
            attached.append(f"chebi:{chebi}")

    if entity_type == CanonicalEntityType.FOOD:
        foods = await search_food(query_name, client, page_size=3)
        if foods:
            fdc_id = foods[0].get("fdcId")
            if fdc_id:
                db.add(
                    EntityExternalId(
                        entity_id_fk=entity.id,
                        source=ExternalIdSource.USDA_FDC.value,
                        external_id=str(fdc_id),
                    )
                )
                attached.append(f"usda_fdc:{fdc_id}")

    return attached


async def process_queue_item(
    db: AsyncSession,
    item: EnrichmentQueueItem,
    *,
    http_client: httpx.AsyncClient | None = None,
) -> EnrichmentQueueItem:
    """Run the candidate curator pipeline for one queue entry."""
    item.status = EnrichmentQueueStatus.IN_PROGRESS.value
    await db.flush()

    owns_client = http_client is None
    client = http_client or httpx.AsyncClient(timeout=20.0)
    try:
        existing = await resolve_entity_by_name(db, item.query_name)
        if existing is not None:
            item.entity_id_fk = existing.id
            item.status = EnrichmentQueueStatus.COMPLETED.value
            item.result_summary = f"Resolved existing entity {existing.entity_id}"
            await db.commit()
            return item

        entity_type = await _infer_entity_type(item.query_name)
        entity = await register_entity(
            db,
            canonical_name=item.query_name,
            display_name=item.query_name,
            entity_type=entity_type,
            coverage_tier=CoverageTier.TIER_C,
            review_status=EntityReviewStatus.MACHINE_GENERATED,
            synonyms=[],
            notes="Created by enrichment worker — pending validation",
        )
        item.entity_id_fk = entity.id

        external_refs = await _attach_external_ids(db, entity, item.query_name, entity_type, client)

        # Candidate composition edges are machine-generated placeholders until validated.
        if entity_type == CanonicalEntityType.FOOD and "anthocyanin" in item.query_normalized:
            compound = await register_entity(
                db,
                canonical_name="Anthocyanins",
                display_name="Anthocyanins",
                entity_type=CanonicalEntityType.COMPOUND,
                coverage_tier=CoverageTier.TIER_B,
                review_status=EntityReviewStatus.MACHINE_GENERATED,
            )
            db.add(
                GraphEdge(
                    source_entity_id=entity.id,
                    target_entity_id=compound.id,
                    relationship_type=GraphRelationshipType.CONTAINS.value,
                    evidence_type=GraphEvidenceType.MECHANISTIC.value,
                    confidence=0.4,
                    review_status=EntityReviewStatus.MACHINE_GENERATED.value,
                    source_provenance="enrichment_worker",
                    notes="Candidate edge — requires human or machine verification",
                )
            )

        item.status = EnrichmentQueueStatus.NEEDS_REVIEW.value
        item.result_summary = (
            f"Registered {entity.entity_id} ({entity_type.value}). "
            f"External refs: {', '.join(external_refs) or 'none'}."
        )
        await db.commit()
        return item
    except Exception as exc:
        logger.exception("Enrichment failed for %s", item.query_name)
        item.status = EnrichmentQueueStatus.FAILED.value
        item.error_message = str(exc)
        await db.commit()
        return item
    finally:
        if owns_client:
            await client.aclose()


async def run_enrichment_batch(
    db: AsyncSession,
    *,
    limit: int = 5,
) -> list[EnrichmentQueueItem]:
    result = await db.execute(
        select(EnrichmentQueueItem)
        .where(EnrichmentQueueItem.status == EnrichmentQueueStatus.PENDING.value)
        .order_by(EnrichmentQueueItem.priority.asc(), EnrichmentQueueItem.created_at.asc())
        .limit(limit)
    )
    items = list(result.scalars().all())
    processed: list[EnrichmentQueueItem] = []
    for item in items:
        processed.append(await process_queue_item(db, item))
    return processed