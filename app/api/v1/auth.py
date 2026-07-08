import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.config import settings
from app.core.security import (
    InvalidTokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

from app.models.enums import AuditAction
from app.models.user import HealthProfile, User
from app.schemas.auth import (
    AuthConfigRead,
    HealthProfileRead,
    HealthProfileUpdate,
    RefreshTokenRequest,
    Token,
    UserCreate,
    UserLogin,
    UserRead,
)
from app.services.audit import record_audit_event

router = APIRouter(prefix="/auth", tags=["auth"])


def _require_local_auth_enabled() -> None:
    if settings.auth_provider == "supabase":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Local registration is disabled. Use Supabase Auth via the workspace login.",
        )


@router.get("/config", response_model=AuthConfigRead)
async def get_auth_config() -> AuthConfigRead:
    return AuthConfigRead(
        auth_provider=settings.auth_provider,
        supabase_url=settings.supabase_url or None,
        supabase_anon_key=settings.supabase_anon_key or settings.supabase_publishable_key or None,
        require_email_verification=settings.require_email_verification,
        allow_guest_auth=settings.allow_guest_auth and settings.auth_provider == "local",
    )


@router.post("/sync", response_model=UserRead)
async def sync_external_user(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Provision or refresh the local user row after Supabase sign-in."""
    if settings.auth_provider != "supabase":
        return current_user

    await record_audit_event(
        db,
        action=AuditAction.USER_SYNC,
        summary=f"User synced via Supabase ({current_user.email})",
        user=current_user,
        request=request,
    )
    await db.commit()
    return current_user


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(
    payload: UserCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    _require_local_auth_enabled()
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        role=payload.role,
        clinic_name=payload.clinic_name,
    )
    db.add(user)
    await db.flush()
    db.add(HealthProfile(user_id=user.id))
    await record_audit_event(
        db,
        action=AuditAction.USER_REGISTERED,
        summary=f"User registered ({user.email})",
        user=user,
        request=request,
    )
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login", response_model=Token)
async def login(payload: UserLogin, request: Request, db: AsyncSession = Depends(get_db)) -> Token:
    _require_local_auth_enabled()
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account is inactive")

    subject = str(user.id)
    await record_audit_event(
        db,
        action=AuditAction.USER_LOGIN,
        summary=f"User signed in ({user.email})",
        user=user,
        request=request,
    )
    await db.commit()
    return Token(access_token=create_access_token(subject), refresh_token=create_refresh_token(subject))


@router.post("/refresh", response_model=Token)
async def refresh_tokens(payload: RefreshTokenRequest, db: AsyncSession = Depends(get_db)) -> Token:
    try:
        subject = decode_token(payload.refresh_token, expected_type="refresh")
        user_id = uuid.UUID(subject)
    except (InvalidTokenError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token") from exc

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    return Token(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.get("/me", response_model=UserRead)
async def get_me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> None:
    await db.delete(current_user)
    await db.commit()


@router.get("/profile", response_model=HealthProfileRead)
async def get_profile(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> HealthProfile:
    result = await db.execute(select(HealthProfile).where(HealthProfile.user_id == current_user.id))
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Health profile not found")
    return profile


@router.put("/profile", response_model=HealthProfileRead)
async def update_profile(
    payload: HealthProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> HealthProfile:
    result = await db.execute(select(HealthProfile).where(HealthProfile.user_id == current_user.id))
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Health profile not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)

    await db.commit()
    await db.refresh(profile)
    return profile
