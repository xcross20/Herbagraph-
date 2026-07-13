import uuid
from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings, settings
from app.core.auth_providers import AuthConfigurationError, verify_external_token
from app.core.security import InvalidTokenError, decode_token, verify_admin_master_token
from app.core.supabase_auth import get_or_create_user_from_supabase
from app.database import AsyncSessionLocal
from app.models.user import User

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def _user_from_local_token(token: str, db: AsyncSession) -> User:
    try:
        subject = decode_token(token, expected_type="access")
        user_id = uuid.UUID(subject)
    except (InvalidTokenError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    return user


async def _user_from_supabase_token(token: str, db: AsyncSession) -> User:
    try:
        claims = await verify_external_token(token)
    except AuthConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    if settings.require_email_verification and not claims.get("email_verified"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email verification required before accessing patient data. Check your inbox.",
        )

    return await get_or_create_user_from_supabase(db, claims)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    if settings.auth_provider == "supabase":
        return await _user_from_supabase_token(credentials.credentials, db)

    return await _user_from_local_token(credentials.credentials, db)


async def get_verified_user(current_user: User = Depends(get_current_user)) -> User:
    """Require a verified email before patient-data operations when configured."""
    if settings.require_email_verification and not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email verification required before accessing patient data.",
        )
    return current_user


async def _admin_email_allowlist() -> set[str]:
    return {
        email.strip().lower() for email in get_settings().admin_emails.split(",") if email.strip()
    }


async def _resolve_admin_user_from_allowlist(db: AsyncSession) -> User:
    admin_emails = await _admin_email_allowlist()
    if not admin_emails:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access is not configured. Set ADMIN_EMAILS in the environment.",
        )
    from sqlalchemy import func

    result = await db.execute(
        select(User).where(func.lower(User.email).in_(admin_emails)).order_by(User.created_at.asc())
    )
    user = result.scalars().first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No admin user account found. Create an account with an ADMIN_EMAILS address first.",
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin user account is inactive")
    return user


async def get_admin_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    token = credentials.credentials
    if verify_admin_master_token(token):
        if not get_settings().admin_master_password.strip():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin master access is disabled")
        return await _resolve_admin_user_from_allowlist(db)

    if settings.auth_provider == "supabase":
        user = await _user_from_supabase_token(token, db)
    else:
        user = await _user_from_local_token(token, db)

    admin_emails = await _admin_email_allowlist()
    if not admin_emails:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access is not configured. Set ADMIN_EMAILS in the environment.",
        )
    if user.email.lower() not in admin_emails:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user