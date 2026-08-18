"""Compare legacy snapshot rebuild vs truth-layer writes without activating production."""

from __future__ import annotations

from dataclasses import dataclass

from app.config import get_settings


@dataclass(frozen=True)
class PathComparison:
    authoritative: bool
    divergences: tuple[str, ...]


def truth_layer_is_authoritative() -> bool:
    """User mutations always use apply_finding_drafts.

    This flag only authorizes apply_snapshot to rebuild findings from the
    engine snapshot. Compare-only mode still persists Ask/answer/note/document
    mutations through the canonical seam.
    """
    return bool(getattr(get_settings(), "discovery_truth_layer_authoritative", False))


def snapshot_rebuild_writes_findings() -> bool:
    return truth_layer_is_authoritative()


def compare_projections(*, legacy_values: list[str], truth_values: list[str]) -> PathComparison:
    left = sorted(legacy_values)
    right = sorted(truth_values)
    divergences = []
    if left != right:
        divergences.append("active_values_differ")
        from app.discovery.telemetry import increment

        increment("dark_launch_divergence")
    return PathComparison(authoritative=truth_layer_is_authoritative(), divergences=tuple(divergences))


def maybe_compare_and_block_write(*, legacy_values: list[str], truth_values: list[str]) -> PathComparison:
    """Compare always. Return authoritative=False to suppress finding writes."""
    comparison = compare_projections(legacy_values=legacy_values, truth_values=truth_values)
    if not comparison.authoritative:
        from app.discovery.telemetry import increment

        increment("dark_launch_write_suppressed")
    return comparison
