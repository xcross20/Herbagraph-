"""Enrichment queue worker."""

from unittest.mock import AsyncMock

import pytest

from app.knowledge_graph.enrichment_worker import enqueue_enrichment, process_queue_item
from app.models.enums import EnrichmentQueueStatus

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_enqueue_deduplicates_pending(db_session):
    first = await enqueue_enrichment(db_session, query_name="Blueberry")
    second = await enqueue_enrichment(db_session, query_name="blueberry")
    await db_session.commit()
    assert first.id == second.id


@pytest.mark.asyncio
async def test_process_queue_item_attaches_usda_fdc_for_food(db_session, monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("USDA_KEY", "test-usda-key")
    get_settings.cache_clear()

    item = await enqueue_enrichment(db_session, query_name="Blueberry")
    await db_session.commit()

    mock_client = AsyncMock()
    search_food = AsyncMock(
        return_value=[{"fdcId": 12345, "description": "Blueberries, raw"}]
    )
    monkeypatch.setattr(
        "app.knowledge_graph.enrichment_worker.get_compound_cid",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "app.knowledge_graph.enrichment_worker.lookup_chebi_id",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr("app.knowledge_graph.enrichment_worker.search_food", search_food)

    processed = await process_queue_item(db_session, item, http_client=mock_client)
    assert "usda_fdc:12345" in (processed.result_summary or "")
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_process_queue_item_registers_entity(db_session, monkeypatch):
    item = await enqueue_enrichment(db_session, query_name="Test Herb XYZ")
    await db_session.commit()

    mock_client = AsyncMock()
    monkeypatch.setattr(
        "app.knowledge_graph.enrichment_worker.get_compound_cid",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "app.knowledge_graph.enrichment_worker.lookup_chebi_id",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "app.knowledge_graph.enrichment_worker.search_food",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "app.knowledge_graph.enrichment_worker.get_compound_synonyms",
        AsyncMock(return_value=[]),
    )

    processed = await process_queue_item(db_session, item, http_client=mock_client)
    assert processed.status in (
        EnrichmentQueueStatus.NEEDS_REVIEW.value,
        EnrichmentQueueStatus.COMPLETED.value,
    )
    assert processed.entity_id_fk is not None


@pytest.mark.asyncio
async def test_deep_enrich_existing_entity_attaches_pubchem(db_session, monkeypatch):
    from app.knowledge_graph.entity_registry import register_entity
    from app.models.enums import CanonicalEntityType, CoverageTier, EntityReviewStatus

    entity = await register_entity(
        db_session,
        canonical_name="Quercetin",
        entity_type=CanonicalEntityType.COMPOUND,
        coverage_tier=CoverageTier.TIER_A,
        review_status=EntityReviewStatus.PRODUCTION_APPROVED,
    )
    await db_session.commit()

    item = await enqueue_enrichment(db_session, query_name="Quercetin")
    await db_session.commit()

    monkeypatch.setattr(
        "app.knowledge_graph.enrichment_worker.get_compound_cid",
        AsyncMock(return_value=5280343),
    )
    monkeypatch.setattr(
        "app.knowledge_graph.enrichment_worker.get_compound_properties",
        AsyncMock(return_value={"IUPACName": "quercetin", "MolecularFormula": "C15H10O7"}),
    )
    monkeypatch.setattr(
        "app.knowledge_graph.enrichment_worker.get_compound_synonyms",
        AsyncMock(return_value=["3,3',4',5,7-Pentahydroxyflavone", "Sophoretin"]),
    )
    monkeypatch.setattr(
        "app.knowledge_graph.enrichment_worker.lookup_chebi_id",
        AsyncMock(return_value="CHEBI:16243"),
    )
    monkeypatch.setattr(
        "app.knowledge_graph.enrichment_worker.search_food",
        AsyncMock(return_value=[]),
    )

    processed = await process_queue_item(db_session, item, http_client=AsyncMock())
    assert processed.entity_id_fk == entity.id
    assert "pubchem:5280343" in (processed.result_summary or "")
    assert processed.status == EnrichmentQueueStatus.NEEDS_REVIEW.value