"""Resolve a raw test label to a canonical catalog test.

Forbidden: substring fallback that maps generic `MRI` to `mri_brain`.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from app.discovery.coverage_catalog import CatalogTest, normalize_label, tests_by_normalized_alias
from app.models.enums import ResolverStatus


@dataclass(frozen=True)
class ResolveResult:
    status: ResolverStatus
    match: CatalogTest | None
    candidates: tuple[CatalogTest, ...]
    raw: str
    normalized: str


@lru_cache(maxsize=1)
def _alias_index() -> dict[str, tuple[CatalogTest, ...]]:
    return {key: tuple(values) for key, values in tests_by_normalized_alias().items()}


def resolve_test(raw_name: str, protocol_text: str | None = None) -> ResolveResult:
    del protocol_text  # protocol is not used to invent a test identity
    normalized = normalize_label(raw_name)
    if not normalized:
        return ResolveResult(ResolverStatus.UNRESOLVED, None, (), raw_name, normalized)
    exact = _alias_index().get(normalized, ())
    unique: dict[str, CatalogTest] = {item.code: item for item in exact}
    if len(unique) == 1:
        match = next(iter(unique.values()))
        return ResolveResult(ResolverStatus.MATCHED, match, (match,), raw_name, normalized)
    if len(unique) > 1:
        return ResolveResult(
            ResolverStatus.AMBIGUOUS,
            None,
            tuple(unique.values()),
            raw_name,
            normalized,
        )
    token_hits = _token_family_hits(normalized)
    if len(token_hits) > 1:
        return ResolveResult(
            ResolverStatus.AMBIGUOUS,
            None,
            tuple(token_hits.values()),
            raw_name,
            normalized,
        )
    return ResolveResult(ResolverStatus.UNRESOLVED, None, (), raw_name, normalized)


def _token_family_hits(normalized: str) -> dict[str, CatalogTest]:
    """Whole-label family clashes only. Never treat containment as a match."""
    if " " in normalized:
        return {}
    hits: dict[str, CatalogTest] = {}
    for key, tests in _alias_index().items():
        tokens = set(key.split())
        if normalized in tokens and len(tests) >= 1:
            for test in tests:
                hits[test.code] = test
    return hits if len(hits) > 1 else {}
