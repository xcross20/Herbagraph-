"""Pluggable authentication provider abstraction (Phase 3 infrastructure).

"Don't build authentication yourself -- use Clerk or Firebase Auth" is good advice
for a real production launch. This module is the integration point for that: set
AUTH_PROVIDER=clerk or AUTH_PROVIDER=firebase (plus the matching credentials) to
switch HerbaGraph over to one of those.

Until real credentials are wired up, the default AUTH_PROVIDER=local keeps the
existing, fully-functional JWT + bcrypt implementation (see app.core.security and
app.api.deps.get_current_user) as the active path -- every test and every existing
flow in this codebase runs against "local" and needs no external account. Selecting
"clerk"/"firebase" without configuring it raises a clear, actionable error rather
than silently falling back to local auth or pretending to authenticate.
"""

from app.config import settings


class AuthConfigurationError(Exception):
    """Raised when a non-default auth provider is selected but not fully configured,
    or when its integration hasn't been implemented yet."""


async def verify_external_token(token: str) -> str:
    """Verify a session token issued by the configured external auth provider and
    return that provider's external user/subject id. Only called when
    settings.auth_provider is not "local" -- app.api.deps.get_current_user still
    uses the built-in JWT path by default.
    """
    if settings.auth_provider == "clerk":
        if not settings.clerk_secret_key:
            raise AuthConfigurationError(
                "AUTH_PROVIDER=clerk but CLERK_SECRET_KEY is not set. Get a secret "
                "key from https://dashboard.clerk.com, set CLERK_SECRET_KEY, and "
                "verify the session token via Clerk's Backend API "
                "(https://clerk.com/docs/reference/backend-api). Or set "
                "AUTH_PROVIDER=local to use HerbaGraph's built-in auth."
            )
        raise AuthConfigurationError(
            "Clerk token verification is not implemented yet. Wire it up in "
            "app.core.auth_providers.verify_external_token, then map the returned "
            "Clerk user id to (or provision) a local User row."
        )

    if settings.auth_provider == "firebase":
        if not settings.firebase_project_id:
            raise AuthConfigurationError(
                "AUTH_PROVIDER=firebase but FIREBASE_PROJECT_ID is not set. Set up "
                "a Firebase project, set FIREBASE_PROJECT_ID, and verify the ID "
                "token via the Firebase Admin SDK (firebase_admin.auth.verify_id_token). "
                "Or set AUTH_PROVIDER=local to use HerbaGraph's built-in auth."
            )
        raise AuthConfigurationError(
            "Firebase token verification is not implemented yet. Wire it up in "
            "app.core.auth_providers.verify_external_token, then map the returned "
            "Firebase uid to (or provision) a local User row."
        )

    raise AuthConfigurationError(
        f"Unknown AUTH_PROVIDER '{settings.auth_provider}'. Expected 'local', 'clerk', or 'firebase'."
    )
