"""Automated expansion worker — candidate graph curation + deep enrichment."""

from __future__ import annotations

import logging

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.integrations.chebi import lookup_chebi_id
from app.integrations.pubchem import get_compound_cid, get_compound_properties, get_compound_synonyms
from app.integrations.usda_fooddata import search_food
from app.knowledge_graph.entity_registry import normalize_entity_name, register_entity, resolve_entity_by_name
from app.models.canonical_entity import (
    CanonicalEntity,
    EnrichmentQueueItem,
    EntityExternalId,
    EntitySynonym,
    GraphEdge,
)
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

_COMPOUND_TYPES = {
    CanonicalEntityType.COMPOUND,
    CanonicalEntityType.NUTRIENT,
    CanonicalEntityType.SUPPLEMENT,
    CanonicalEntityType.BOTANICAL,
    CanonicalEntityType.PEPTIDE,
}
_FOOD_TYPES = {
    CanonicalEntityType.FOOD,
    CanonicalEntityType.BOTANICAL,
}


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


async def enqueue_missing_external_ids(
    db: AsyncSession,
    *,
    limit: int = 50,
    requested_by: str | None = None,
    priority: int = 50,
) -> dict[str, int]:
    """Queue production/tier-A entities that still lack PubChem/ChEBI/USDA external IDs."""
    entities = list(
        (
            await db.execute(
                select(CanonicalEntity)
                .options(selectinload(CanonicalEntity.external_ids))
                .where(
                    CanonicalEntity.coverage_tier.in_(
                        [CoverageTier.TIER_A.value, CoverageTier.TIER_B.value]
                    )
                )
                .order_by(CanonicalEntity.created_at.asc())
                .limit(limit * 3)
            )
        ).scalars().all()
    )
    enqueued = 0
    skipped = 0
    for entity in entities:
        if enqueued >= limit:
            break
        if entity.external_ids:
            skipped += 1
            continue
        await enqueue_enrichment(
            db,
            query_name=entity.canonical_name,
            priority=priority,
            requested_by=requested_by,
        )
        enqueued += 1
    await db.commit()
    return {"enqueued": enqueued, "skipped_with_ids": skipped, "scanned": len(entities)}


async def _infer_entity_type(query_name: str) -> CanonicalEntityType:
    lowered = query_name.lower()
    if any(token in lowered for token in ("extract", "supplement", "capsule", "tablet")):
        return CanonicalEntityType.SUPPLEMENT
    if any(token in lowered for token in ("acid", "flavonoid", "polyphenol", "curcumin", "quercetin")):
        return CanonicalEntityType.COMPOUND
    if any(token in lowered for token in ("tea", "root", "bark", "herb", "ginseng", "turmeric")):
        return CanonicalEntityType.BOTANICAL
    return CanonicalEntityType.FOOD


def _entity_type_enum(value: str | CanonicalEntityType) -> CanonicalEntityType:
    if isinstance(value, CanonicalEntityType):
        return value
    try:
        return CanonicalEntityType(value)
    except ValueError:
        return CanonicalEntityType.SUPPLEMENT


async def _existing_external_sources(db: AsyncSession, entity_id) -> set[str]:
    rows = (
        await db.execute(
            select(EntityExternalId.source).where(EntityExternalId.entity_id_fk == entity_id)
        )
    ).all()
    return {row[0] for row in rows}


async def _add_synonyms(db: AsyncSession, entity, synonyms: list[str]) -> int:
    if not synonyms:
        return 0
    existing = (
        await db.execute(
            select(EntitySynonym.synonym_normalized).where(EntitySynonym.entity_id_fk == entity.id)
        )
    ).all()
    have = {row[0] for row in existing}
    added = 0
    for synonym in synonyms:
        cleaned = synonym.strip()
        if not cleaned:
            continue
        normalized = normalize_entity_name(cleaned)
        if not normalized or normalized in have:
            continue
        db.add(
            EntitySynonym(
                entity_id_fk=entity.id,
                synonym=cleaned,
                synonym_normalized=normalized,
            )
        )
        have.add(normalized)
        added += 1
    return added


async def _attach_external_ids(
    db: AsyncSession,
    entity,
    query_name: str,
    entity_type: CanonicalEntityType,
    client: httpx.AsyncClient,
) -> list[str]:
    attached: list[str] = []
    have = await _existing_external_sources(db, entity.id)

    if entity_type in _COMPOUND_TYPES and ExternalIdSource.PUBCHEM.value not in have:
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
                iupac = props.get("IUPACName") or ""
                formula = props.get("MolecularFormula") or ""
                note = f"PubChem CID {cid}"
                if formula:
                    note += f" ({formula})"
                if iupac:
                    note += f": {iupac}"
                entity.notes = ((entity.notes or "") + f"\n{note}").strip()
            synonyms = await get_compound_synonyms(cid, client, limit=10)
            await _add_synonyms(db, entity, synonyms)

    if entity_type in _COMPOUND_TYPES and ExternalIdSource.CHEBI.value not in have:
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

    if entity_type in _FOOD_TYPES and ExternalIdSource.USDA_FDC.value not in have:
        foods = await search_food(query_name, client, page_size=8)
        if foods:
            best = foods[0]
            fdc_id = best.get("fdcId")
            if fdc_id:
                db.add(
                    EntityExternalId(
                        entity_id_fk=entity.id,
                        source=ExternalIdSource.USDA_FDC.value,
                        external_id=str(fdc_id),
                    )
                )
                attached.append(f"usda_fdc:{fdc_id}")
                desc = best.get("description") or ""
                dtype = best.get("dataType") or ""
                entity.notes = (
                    (entity.notes or "") + f"\nUSDA FDC {fdc_id} ({dtype}): {desc}"
                ).strip()

    return attached


async def _maybe_candidate_composition(
    db: AsyncSession, entity, entity_type: CanonicalEntityType, query_normalized: str
) -> None:
    """Lightweight candidate CONTAINS edges for well-known composition patterns."""
    if entity_type != CanonicalEntityType.FOOD:
        return
    compound_name = None
    if "anthocyanin" in query_normalized or "blueberr" in query_normalized:
        compound_name = "Anthocyanins"
    elif "curcumin" in query_normalized or "turmeric" in query_normalized:
        compound_name = "Curcumin"
    elif "quercetin" in query_normalized or "onion" in query_normalized:
        compound_name = "Quercetin"
    if not compound_name:
        return

    compound = await register_entity(
        db,
        canonical_name=compound_name,
        display_name=compound_name,
        entity_type=CanonicalEntityType.COMPOUND,
        coverage_tier=CoverageTier.TIER_B,
        review_status=EntityReviewStatus.MACHINE_GENERATED,
    )
    existing_edge = await db.execute(
        select(GraphEdge)
        .where(
            GraphEdge.source_entity_id == entity.id,
            GraphEdge.target_entity_id == compound.id,
            GraphEdge.relationship_type == GraphRelationshipType.CONTAINS.value,
        )
        .limit(1)
    )
    if existing_edge.scalar_one_or_none() is not None:
        return
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


async def process_queue_item(
    db: AsyncSession,
    item: EnrichmentQueueItem,
    *,
    http_client: httpx.AsyncClient | None = None,
) -> EnrichmentQueueItem:
    """Run the candidate curator / deep enrichment pipeline for one queue entry."""
    item.status = EnrichmentQueueStatus.IN_PROGRESS.value
    await db.flush()

    owns_client = http_client is None
    client = http_client or httpx.AsyncClient(timeout=20.0)
    try:
        existing = await resolve_entity_by_name(db, item.query_name)
        if existing is not None:
            item.entity_id_fk = existing.id
            entity_type = _entity_type_enum(existing.entity_type)
            external_refs = await _attach_external_ids(
                db, existing, item.query_name, entity_type, client
            )
            await _maybe_candidate_composition(db, existing, entity_type, item.query_normalized)
            if external_refs:
                item.status = EnrichmentQueueStatus.NEEDS_REVIEW.value
                item.result_summary = (
                    f"Deep-enriched existing entity {existing.entity_id}. "
                    f"External refs: {', '.join(external_refs)}."
                )
            else:
                item.status = EnrichmentQueueStatus.COMPLETED.value
                item.result_summary = (
                    f"Resolved existing entity {existing.entity_id} "
                    f"(no new external IDs attached)."
                )
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
        await _maybe_candidate_composition(db, entity, entity_type, item.query_normalized)

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
