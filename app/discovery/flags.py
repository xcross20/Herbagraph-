"""Feature flags for Discovery V2. Persist stays off until investigation invariants pass."""

from __future__ import annotations


def _settings():
    from app.config import get_settings

    return get_settings()


def discovery_v2_enabled() -> bool:
    return bool(getattr(_settings(), "discovery_investigation_state_v2", False))


def discovery_append_only() -> bool:
    return bool(getattr(_settings(), "discovery_append_only_findings", False))


def discovery_coverage_enabled() -> bool:
    return bool(getattr(_settings(), "discovery_coverage_graph_enabled", False))
