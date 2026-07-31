import time

import pytest
from jose import jwt

from app.core.supabase_auth import SupabaseAuthError, verify_supabase_access_token


def _make_token(secret: str, *, email: str = "clinician@example.com", verified: bool = True) -> str:
    now = int(time.time())
    payload = {
        "sub": "550e8400-e29b-41d4-a716-446655440000",
        "email": email,
        "role": "authenticated",
        "aud": "authenticated",
        "email_verified": verified,
        "iat": now,
        "exp": now + 3600,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def test_verify_supabase_token_success(monkeypatch):
    secret = "test-supabase-jwt-secret-32chars!!"
    monkeypatch.setattr("app.core.supabase_auth.settings.supabase_url", "https://example.supabase.co")
    monkeypatch.setattr("app.core.supabase_auth.settings.supabase_jwt_secret", secret)
    token = _make_token(secret)
    claims = verify_supabase_access_token(token)
    assert claims["email"] == "clinician@example.com"
    assert claims["email_verified"] is True


def test_verify_supabase_token_rejects_invalid(monkeypatch):
    monkeypatch.setattr("app.core.supabase_auth.settings.supabase_url", "https://example.supabase.co")
    monkeypatch.setattr("app.core.supabase_auth.settings.supabase_jwt_secret", "secret-a")
    token = _make_token("secret-b")
    with pytest.raises(SupabaseAuthError):
        verify_supabase_access_token(token)


def test_verify_supabase_token_requires_url(monkeypatch):
    monkeypatch.setattr("app.core.supabase_auth.settings.supabase_url", "")
    with pytest.raises(SupabaseAuthError, match="SUPABASE_URL"):
        verify_supabase_access_token("not-a-real-token")