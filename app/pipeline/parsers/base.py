"""Shared types for provider-specific lab parsers."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.schemas.pipeline import ParsedLabResult


@dataclass
class ParserPassResult:
    results: list[ParsedLabResult] = field(default_factory=list)
    consumed_line_indices: set[int] = field(default_factory=set)


def dedupe_parsed_results(results: list[ParsedLabResult]) -> list[ParsedLabResult]:
    """Keep highest-confidence row per (test name, value) pair."""
    best: dict[tuple[str, float], ParsedLabResult] = {}
    for row in results:
        key = (row.raw_test_name.lower(), round(row.value, 4))
        existing = best.get(key)
        if existing is None or (row.parse_confidence or 0) >= (existing.parse_confidence or 0):
            best[key] = row
    return list(best.values())