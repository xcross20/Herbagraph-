from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.security import create_access_token, create_refresh_token, hash_password, verify_password
from app.models.user import HealthProfile, User
from app.schemas.auth import (
    HealthProfileRead,
    HealthProfileUpdate,
    Token,
    UserCreate,
    UserLogin,
    UserRead,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(payload: UserCreate, db: AsyncSession = Depends(get_db)) -> User:
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(email=payload.email, hashed_password=hash_password(payload.password))
    db.add(user)
    await db.flush()
    db.add(HealthProfile(user_id=user.id))
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login", response_model=Token)
async def login(payload: UserLogin, db: AsyncSession = Depends(get_db)) -> Token:
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account is inactive")

    subject = str(user.id)
    return Token(access_token=create_access_token(subject), refresh_token=create_refresh_token(subject))


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
