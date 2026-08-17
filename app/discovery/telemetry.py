"""PHI-safe Discovery counters. Never log narratives or reports."""

from __future__ import annotations

from collections import Counter

_COUNTERS: Counter[str] = Counter()


def increment(name: str, amount: int = 1) -> None:
    _COUNTERS[name] += amount


def snapshot() -> dict[str, int]:
    return dict(_COUNTERS)


def reset() -> None:
    _COUNTERS.clear()
