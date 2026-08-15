"""Feature flags for Discovery V2. Defaults on; existing orchestrate() stays callable."""

from __future__ import annotations


def _settings():
    from app.config import get_settings

    return get_settings()


def discovery_v2_enabled() -> bool:
    return bool(getattr(_settings(), "discovery_investigation_state_v2", True))


def discovery_append_only() -> bool:
    return bool(getattr(_settings(), "discovery_append_only_findings", True))


def discovery_coverage_enabled() -> bool:
    return bool(getattr(_settings(), "discovery_coverage_graph_enabled", True))
