import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.config import get_settings, settings
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
from app.core.oauth import google_oauth_enabled
from app.core.signup_access import (
    apply_signup_approval_token,
    approve_email_for_signup,
    issue_signup_approval_token,
    require_approved_email,
    signup_access_required,
    verify_access_code,
)
from app.core.supabase_auth import SupabaseAuthError, verify_supabase_access_token
from app.schemas.auth import (
    AccessCodeOnlyVerify,
    AuthConfigRead,
    HealthProfileRead,
    HealthProfileUpdate,
    RefreshTokenRequest,
    SignupAccessVerify,
    SignupApprovalTokenRead,
    Token,
    UserCreate,
    UserLogin,
    UserRead,
)
from app.services.audit import record_audit_event

router = APIRouter(prefix="/auth", tags=["auth"])
_bearer_scheme = HTTPBearer(auto_error=False)


def _require_local_auth_enabled() -> None:
    if settings.auth_provider == "supabase":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Local registration is disabled. Use Supabase Auth via the workspace login.",
        )


@router.get("/config", response_model=AuthConfigRead)
async def get_auth_config() -> AuthConfigRead:
    cfg = get_settings()
    return AuthConfigRead(
        auth_provider=cfg.auth_provider,
        supabase_url=cfg.supabase_url or None,
        supabase_anon_key=cfg.supabase_anon_key or cfg.supabase_publishable_key or None,
        require_email_verification=cfg.require_email_verification,
        allow_guest_auth=cfg.allow_guest_auth and cfg.auth_provider == "local",
        signup_access_required=signup_access_required(),
        google_oauth_enabled=google_oauth_enabled(),
    )


@router.post("/verify-signup-access", status_code=status.HTTP_204_NO_CONTENT)
async def verify_signup_access(payload: SignupAccessVerify) -> None:
    """Gate private-preview signups; call before Supabase or local registration."""
    verify_access_code(payload.access_code)
    approve_email_for_signup(payload.email)


@router.post("/verify-access-code", response_model=SignupApprovalTokenRead)
async def verify_access_code_for_oauth(payload: AccessCodeOnlyVerify) -> SignupApprovalTokenRead:
    """Verify preview access code and issue a short-lived token for Google OAuth signup."""
    if not signup_access_required():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Signup access code is not required for this environment.",
        )
    return SignupApprovalTokenRead(approval_token=issue_signup_approval_token(payload.access_code))


@router.post("/sync", response_model=UserRead)
async def sync_external_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Provision or refresh the local user row after Supabase or OAuth sign-in."""
    if settings.auth_provider != "supabase":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account sync is only used with Supabase Auth.",
        )
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    try:
        claims = verify_supabase_access_token(credentials.credentials)
    except SupabaseAuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    if settings.require_email_verification and not claims.get("email_verified"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email verification required before accessing patient data. Check your inbox.",
        )

    approval_token = request.headers.get("X-Signup-Approval-Token")
    apply_signup_approval_token(approval_token, claims["email"])

    from app.core.supabase_auth import get_or_create_user_from_supabase

    try:
        user = await get_or_create_user_from_supabase(db, claims)
    except HTTPException:
        raise

    await record_audit_event(
        db,
        action=AuditAction.USER_SYNC,
        summary=f"User synced via Supabase ({user.email})",
        user=user,
        request=request,
    )
    await db.commit()
    await db.refresh(user)
    return user


def _is_guest_email(email: str) -> bool:
    lowered = (email or "").strip().lower()
    return lowered.endswith("@guest.herbagraph-app.io") or lowered.startswith("guest-")


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(
    payload: UserCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    _require_local_auth_enabled()
    if _is_guest_email(payload.email) and not get_settings().allow_guest_auth:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Guest accounts are disabled. Create a registered account with your email.",
        )
    if payload.access_code:
        verify_access_code(payload.access_code)
        approve_email_for_signup(payload.email)
    require_approved_email(payload.email)
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
