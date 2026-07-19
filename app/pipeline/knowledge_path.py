"""Helpers for knowledge_path validation and defaults."""

from __future__ import annotations

from app.models.enums import KnowledgePath

DEFAULT_KNOWLEDGE_PATH = KnowledgePath.LEGACY


def parse_knowledge_path(value: str | KnowledgePath | None) -> KnowledgePath:
    if value is None or value == "":
        return DEFAULT_KNOWLEDGE_PATH
    if isinstance(value, KnowledgePath):
        return value
    normalized = str(value).strip().lower()
    try:
        return KnowledgePath(normalized)
    except ValueError as exc:
        raise ValueError(
            f"Invalid knowledge_path '{value}'. Use 'legacy' or 'canonical'."
        ) from exc
