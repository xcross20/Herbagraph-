"""Confidence scoring for parsed lab rows."""

from __future__ import annotations

from app.pipeline.user_biomarker_profile import resolve_canonical_name
from app.schemas.pipeline import ParsedLabResult

_PATTERN_BASE: dict[str, float] = {
    "table_extraction": 0.88,
    "healow_sliding_window": 0.82,
    "healow_line": 0.9,
    "generic_regex": 0.85,
    "generic_sliding_window": 0.75,
    "llm_extraction": 0.7,
}

_JUNK_NAME_TOKENS = frozenset(
    {
        "result",
        "flag",
        "reference",
        "range",
        "units",
        "unit",
        "component",
        "test name",
        "out of range",
        "final result",
        "accession",
        "collection date",
        "ordering physician",
    }
)


def score_parsed_result(result: ParsedLabResult) -> float:
    """Compute 0-1 confidence from parser pattern, alias resolution, and field completeness."""
    base = _PATTERN_BASE.get(result.parser_pattern or "generic_regex", 0.7)
    score = base

    canonical = resolve_canonical_name(result.raw_test_name)
    if canonical:
        score += 0.08
    elif _looks_like_junk_name(result.raw_test_name):
        score -= 0.35

    if result.unit:
        score += 0.04
    if result.reference_range_low is not None or result.reference_range_high is not None:
        score += 0.04
    if result.qualitative_result:
        score += 0.03

    return round(max(0.0, min(1.0, score)), 3)


def _looks_like_junk_name(name: str) -> bool:
    lowered = name.strip().lower()
    if not lowered or len(lowered) < 2:
        return True
    return lowered in _JUNK_NAME_TOKENS or any(token in lowered for token in ("accession id", "report:"))


def apply_confidence_scores(
    results: list[ParsedLabResult],
    *,
    document_provider: str | None = None,
) -> list[ParsedLabResult]:
    scored: list[ParsedLabResult] = []
    for row in results:
        confidence = row.parse_confidence if row.parse_confidence is not None else score_parsed_result(row)
        scored.append(
            row.model_copy(
                update={
                    "parse_confidence": confidence,
                    "document_provider": row.document_provider or document_provider,
                }
            )
        )
    return scored