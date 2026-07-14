"""OAuth availability helpers (Google via Supabase Auth)."""

from __future__ import annotations

from app.config import settings
from app.core.supabase_auth import supabase_configured


def google_oauth_enabled() -> bool:
    """True when Google sign-in should be exposed to the frontend."""
    return (
        settings.google_oauth_enabled
        and settings.auth_provider == "supabase"
        and supabase_configured()
    )