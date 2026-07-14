from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return _pwd_context.verify(plain_password, hashed_password)


def _create_token(
    subject: str,
    expires_delta: timedelta,
    token_type: Literal["access", "refresh", "admin_master", "signup_approval"],
) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def create_access_token(subject: str) -> str:
    return _create_token(
        subject,
        timedelta(minutes=settings.access_token_expire_minutes),
        "access",
    )


def create_refresh_token(subject: str) -> str:
    return _create_token(
        subject,
        timedelta(days=settings.refresh_token_expire_days),
        "refresh",
    )


class InvalidTokenError(Exception):
    pass


def create_admin_master_token() -> str:
    return _create_token(
        "master",
        timedelta(hours=12),
        "admin_master",
    )


def create_signup_approval_token() -> str:
    """Short-lived token proving signup access code was verified (OAuth signup flow)."""
    return _create_token(
        "signup_gate",
        timedelta(minutes=15),
        "signup_approval",
    )


def verify_signup_approval_token(token: str) -> bool:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError:
        return False
    return payload.get("type") == "signup_approval" and payload.get("sub") == "signup_gate"


def verify_admin_master_token(token: str) -> bool:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError:
        return False
    return payload.get("type") == "admin_master" and payload.get("sub") == "master"


def decode_token(token: str, expected_type: Literal["access", "refresh"] = "access") -> str:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError as exc:
        raise InvalidTokenError("Could not validate token") from exc

    if payload.get("type") != expected_type:
        raise InvalidTokenError(f"Expected a {expected_type} token")

    subject = payload.get("sub")
    if subject is None:
        raise InvalidTokenError("Token missing subject")
    return subject
