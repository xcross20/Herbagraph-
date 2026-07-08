"""Supabase Auth JWT verification and local user provisioning."""

from __future__ import annotations

import secrets
import uuid

from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import hash_password
from app.models.user import HealthProfile, User


class SupabaseAuthError(Exception):
    pass


def verify_supabase_access_token(token: str) -> dict:
    """Verify a Supabase-issued JWT and return its claims."""
    if not settings.supabase_jwt_secret:
        raise SupabaseAuthError(
            "SUPABASE_JWT_SECRET is not configured. Copy the JWT secret from your Supabase "
            "project settings (Settings → API → JWT Secret)."
        )
    try:
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
            options={"verify_aud": True},
        )
    except JWTError as exc:
        raise SupabaseAuthError("Invalid or expired Supabase token") from exc

    if payload.get("role") not in {"authenticated", "service_role"}:
        raise SupabaseAuthError("Token is not an authenticated user session")

    sub = payload.get("sub")
    if not sub:
        raise SupabaseAuthError("Token missing subject")

    email = payload.get("email") or (payload.get("user_metadata") or {}).get("email")
    if not email:
        raise SupabaseAuthError("Token missing email claim")

    email_verified = bool(payload.get("email_verified"))
    if not email_verified:
        # Supabase may nest confirmation in app_metadata
        app_meta = payload.get("app_metadata") or {}
        email_verified = bool(app_meta.get("email_verified"))

    return {
        "sub": str(sub),
        "email": str(email).lower(),
        "email_verified": email_verified,
        "full_name": (payload.get("user_metadata") or {}).get("full_name"),
    }


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

    user.is_verified = bool(claims.get("email_verified", user.is_verified))
    if claims.get("full_name") and not user.full_name:
        user.full_name = claims["full_name"]

    await db.commit()
    await db.refresh(user)
    return user


def supabase_configured() -> bool:
    return bool(settings.supabase_url and settings.supabase_jwt_secret and settings.supabase_anon_key)