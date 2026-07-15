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

    processed = await process_queue_item(db_session, item, http_client=mock_client)
    assert processed.status in (
        EnrichmentQueueStatus.NEEDS_REVIEW.value,
        EnrichmentQueueStatus.COMPLETED.value,
    )
    assert processed.entity_id_fk is not None