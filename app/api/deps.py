import uuid
from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.auth_providers import AuthConfigurationError, verify_external_token
from app.core.security import InvalidTokenError, decode_token
from app.database import AsyncSessionLocal
from app.models.user import User

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    if settings.auth_provider != "local":
        # Phase 3 integration point -- see app/core/auth_providers.py. Not implemented
        # yet, so this always raises 501 rather than silently falling back to local
        # auth or pretending a token verified.
        try:
            await verify_external_token(credentials.credentials)
        except AuthConfigurationError as exc:
            raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc)) from exc

    try:
        subject = decode_token(credentials.credentials, expected_type="access")
    except InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    try:
        user_id = uuid.UUID(subject)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject") from exc

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    return user
