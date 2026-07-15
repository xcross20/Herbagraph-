"""Synonym resolution helpers for ingestion and enrichment."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge_graph.entity_registry import normalize_entity_name, resolve_entity_by_name
from app.models.canonical_entity import CanonicalEntity
from app.models.enums import CanonicalEntityType


async def resolve_or_none(
    db: AsyncSession,
    name: str,
    *,
    entity_type: CanonicalEntityType | None = None,
) -> CanonicalEntity | None:
    return await resolve_entity_by_name(db, name, entity_type=entity_type)


def suggest_canonical_name(raw_name: str) -> str:
    """Light normalization for candidate ingestion — not a taxonomic authority."""
    cleaned = " ".join(raw_name.split())
    return cleaned[:1].upper() + cleaned[1:] if cleaned else cleaned


async def check_duplicate_candidates(
    db: AsyncSession,
    names: list[str],
    *,
    entity_type: CanonicalEntityType | None = None,
) -> dict[str, CanonicalEntity | None]:
    return {
        name: await resolve_entity_by_name(db, name, entity_type=entity_type) for name in names
    }


def normalized_key(name: str) -> str:
    return normalize_entity_name(name)