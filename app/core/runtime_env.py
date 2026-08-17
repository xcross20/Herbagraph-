"""Public, non-secret runtime plane (local / uat / preview / production)."""

from __future__ import annotations

import os

def runtime_environment() -> str:
    explicit = (
        os.environ.get("APP_ENV") or os.environ.get("HERBAGRAPH_ENV") or ""
    ).strip().lower()
    if explicit:
        return explicit
    railway = (os.environ.get("RAILWAY_ENVIRONMENT_NAME") or "").strip().lower()
    if railway:
        return railway
    return "local"


def is_production() -> bool:
    return runtime_environment() == "production"
