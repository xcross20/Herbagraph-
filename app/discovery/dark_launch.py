"""Compare legacy snapshot rebuild vs truth-layer writes without activating production."""

from __future__ import annotations

from dataclasses import dataclass

from app.config import get_settings


@dataclass(frozen=True)
class PathComparison:
    authoritative: bool
    divergences: tuple[str, ...]


def truth_layer_is_authoritative() -> bool:
    return bool(getattr(get_settings(), "discovery_truth_layer_authoritative", False))


def compare_projections(*, legacy_values: list[str], truth_values: list[str]) -> PathComparison:
    left = sorted(legacy_values)
    right = sorted(truth_values)
    divergences = []
    if left != right:
        divergences.append("active_values_differ")
    return PathComparison(authoritative=truth_layer_is_authoritative(), divergences=tuple(divergences))
