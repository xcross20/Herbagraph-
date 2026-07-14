"""Pre-launch signup gate: verify access code before account creation."""

from __future__ import annotations

import time

from fastapi import HTTPException, status

from app.config import settings
from app.core.security import create_signup_approval_token, verify_signup_approval_token

# email -> expiry unix timestamp (short-lived approval after code check)
_approved_emails: dict[str, float] = {}
_APPROVAL_TTL_SECONDS = 900  # 15 minutes


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def signup_access_required() -> bool:
    return bool(settings.signup_access_code.strip())


def verify_access_code(access_code: str) -> None:
    expected = settings.signup_access_code.strip()
    if not expected:
        return
    if (access_code or "").strip() != expected:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid access code. HerbaGraph is in private preview — contact the team for access.",
        )


def approve_email_for_signup(email: str) -> None:
    _approved_emails[_normalize_email(email)] = time.time() + _APPROVAL_TTL_SECONDS


def _prune_expired() -> None:
    now = time.time()
    expired = [email for email, expiry in _approved_emails.items() if expiry <= now]
    for email in expired:
        _approved_emails.pop(email, None)


def issue_signup_approval_token(access_code: str) -> str:
    """Verify access code and return a short-lived OAuth signup approval token."""
    verify_access_code(access_code)
    return create_signup_approval_token()


def apply_signup_approval_token(token: str | None, email: str) -> None:
    """If signup is gated, allow OAuth registration when a valid approval token is presented."""
    if not signup_access_required() or not token:
        return
    if verify_signup_approval_token(token):
        approve_email_for_signup(email)


def require_approved_email(email: str) -> None:
    if not signup_access_required():
        return
    _prune_expired()
    key = _normalize_email(email)
    expiry = _approved_emails.get(key)
    if expiry is None or expiry <= time.time():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Signup access code required. Enter a valid access code on the signup page.",
        )
    _approved_emails.pop(key, None)