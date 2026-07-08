"""Pluggable authentication provider abstraction."""

from app.config import settings
from app.core.supabase_auth import SupabaseAuthError, verify_supabase_access_token


class AuthConfigurationError(Exception):
    """Raised when a non-default auth provider is selected but not fully configured."""


async def verify_external_token(token: str) -> dict:
    """Verify a session token from the configured external auth provider."""
    if settings.auth_provider == "supabase":
        try:
            return verify_supabase_access_token(token)
        except SupabaseAuthError as exc:
            raise AuthConfigurationError(str(exc)) from exc

    if settings.auth_provider == "clerk":
        if not settings.clerk_secret_key:
            raise AuthConfigurationError(
                "AUTH_PROVIDER=clerk but CLERK_SECRET_KEY is not set. "
                "Or set AUTH_PROVIDER=local or AUTH_PROVIDER=supabase."
            )
        raise AuthConfigurationError("Clerk token verification is not implemented yet.")

    if settings.auth_provider == "firebase":
        if not settings.firebase_project_id:
            raise AuthConfigurationError(
                "AUTH_PROVIDER=firebase but FIREBASE_PROJECT_ID is not set. "
                "Or set AUTH_PROVIDER=local or AUTH_PROVIDER=supabase."
            )
        raise AuthConfigurationError("Firebase token verification is not implemented yet.")

    raise AuthConfigurationError(
        f"Unknown AUTH_PROVIDER '{settings.auth_provider}'. Expected 'local' or 'supabase'."
    )