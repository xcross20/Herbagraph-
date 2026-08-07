"""Supabase Auth JWT verification and local user provisioning."""

from __future__ import annotations

import secrets
import time

import httpx
from jose import JWTError, jwk, jwt
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.signup_access import require_approved_email, signup_access_required
from app.core.security import hash_password
from app.models.user import HealthProfile, User

_JWKS_CACHE: dict | None = None
_JWKS_CACHE_AT: float = 0.0
_JWKS_TTL_SECONDS = 3600


class SupabaseAuthError(Exception):
    pass


def _effective_anon_key() -> str:
    return settings.supabase_anon_key or settings.supabase_publishable_key


def _fetch_jwks() -> dict:
    global _JWKS_CACHE, _JWKS_CACHE_AT
    now = time.monotonic()
    if _JWKS_CACHE is not None and (now - _JWKS_CACHE_AT) < _JWKS_TTL_SECONDS:
        return _JWKS_CACHE

    if not settings.supabase_url:
        raise SupabaseAuthError("SUPABASE_URL is not configured.")

    url = f"{settings.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
    try:
        response = httpx.get(url, timeout=10.0)
        response.raise_for_status()
        _JWKS_CACHE = response.json()
        _JWKS_CACHE_AT = now
        return _JWKS_CACHE
    except httpx.HTTPError as exc:
        raise SupabaseAuthError(f"Could not fetch Supabase JWKS: {exc}") from exc


def _decode_with_jwks(token: str) -> dict:
    header = jwt.get_unverified_header(token)
    kid = header.get("kid")
    if not kid:
        raise SupabaseAuthError("Token header missing key id (kid)")

    jwks = _fetch_jwks()
    keys = jwks.get("keys") or []
    matching = next((k for k in keys if k.get("kid") == kid), None)
    if matching is None:
        raise SupabaseAuthError("No matching Supabase signing key found for token")

    key = jwk.construct(matching)
    return jwt.decode(
        token,
        key,
        algorithms=[matching.get("alg", "ES256")],
        audience="authenticated",
        options={"verify_aud": True},
    )


def _decode_with_hs256_secret(token: str) -> dict:
    if not settings.supabase_jwt_secret:
        raise SupabaseAuthError("SUPABASE_JWT_SECRET is not configured.")
    return jwt.decode(
        token,
        settings.supabase_jwt_secret,
        algorithms=["HS256"],
        audience="authenticated",
        options={"verify_aud": True},
    )


def _claims_from_payload(payload: dict) -> dict:
    if payload.get("role") not in {"authenticated", "service_role"}:
        raise SupabaseAuthError("Token is not an authenticated user session")

    sub = payload.get("sub")
    if not sub:
        raise SupabaseAuthError("Token missing subject")

    meta = payload.get("user_metadata") or {}
    app_meta = payload.get("app_metadata") or {}
    email = payload.get("email") or meta.get("email") or app_meta.get("email")
    if not email:
        raise SupabaseAuthError("Token missing email claim")

    # Supabase tokens vary: email_verified bool, or email_confirmed_at timestamp.
    email_verified = bool(payload.get("email_verified"))
    if not email_verified:
        email_verified = bool(app_meta.get("email_verified"))
    if not email_verified and payload.get("email_confirmed_at"):
        email_verified = True
    # After successful email-link confirm, session is authenticated — treat as verified.
    if not email_verified and payload.get("role") == "authenticated":
        # Prefer explicit true when present; otherwise allow verified for confirmed sessions
        # when confirmation is enforced only client-side (REQUIRE_EMAIL_VERIFICATION).
        email_verified = bool(meta.get("email_verified")) or email_verified

    full_name = meta.get("full_name") or meta.get("name") or meta.get("fullName")
    signup_gate = meta.get("hg_signup_gate")
    return {
        "sub": str(sub),
        "email": str(email).lower(),
        "email_verified": email_verified,
        "full_name": full_name,
        "auth_method": app_meta.get("provider"),
        "signup_gate": signup_gate,
    }


def verify_supabase_access_token(token: str) -> dict:
    """Verify a Supabase-issued JWT and return its claims."""
    if not settings.supabase_url:
        raise SupabaseAuthError("SUPABASE_URL is not configured.")

    try:
        if settings.supabase_jwt_secret:
            payload = _decode_with_hs256_secret(token)
        else:
            payload = _decode_with_jwks(token)
    except JWTError as exc:
        raise SupabaseAuthError("Invalid or expired Supabase token") from exc

    return _claims_from_payload(payload)


async def get_or_create_user_from_supabase(db: AsyncSession, claims: dict) -> User:
    """Map a verified Supabase identity to a local HerbaGraph user row."""
    external_id = claims["sub"]
    email = claims["email"]

    result = await db.execute(select(User).where(User.external_auth_id == external_id))
    user = result.scalar_one_or_none()

    if user is None:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user is not None:
            user.external_auth_id = external_id
            user.auth_provider = "supabase"
            if claims.get("full_name") and not user.full_name:
                user.full_name = claims["full_name"]
        else:
            # Private preview: accept durable gate from Supabase user_metadata
            # (set at signUp after access-code check). Do NOT rely only on
            # in-memory approval — email confirm links often arrive after TTL
            # or hit a different Railway worker.
            if signup_access_required() and claims.get("signup_gate") != "ok":
                require_approved_email(email)
            user = User(
                email=email,
                hashed_password=hash_password(secrets.token_urlsafe(48)),
                auth_provider="supabase",
                external_auth_id=external_id,
                is_verified=claims.get("email_verified", False),
                full_name=claims.get("full_name"),
            )
            db.add(user)
            await db.flush()
            db.add(HealthProfile(user_id=user.id))

    if claims.get("email_verified"):
        user.is_verified = True
    else:
        user.is_verified = bool(user.is_verified)
    if claims.get("full_name") and not user.full_name:
        user.full_name = claims["full_name"]

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        result = await db.execute(select(User).where(User.external_auth_id == external_id))
        user = result.scalar_one_or_none()
        if user is None:
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()
        if user is None:
            raise
    await db.refresh(user)
    return user


def supabase_configured() -> bool:
    return bool(settings.supabase_url and _effective_anon_key())