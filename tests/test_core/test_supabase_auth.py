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


def _unsigned_header_token(alg: str) -> str:
    import base64
    import json

    def b64(obj: dict) -> str:
        raw = json.dumps(obj, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    return f"{b64({'alg': alg, 'kid': 'test-kid', 'typ': 'JWT'})}.{b64({'sub': 'x'})}.sig"


def test_es256_token_uses_jwks_even_when_hs_secret_set(monkeypatch):
    monkeypatch.setattr("app.core.supabase_auth.settings.supabase_url", "https://example.supabase.co")
    monkeypatch.setattr("app.core.supabase_auth.settings.supabase_jwt_secret", "legacy-hs256-secret")

    def fake_jwks(_token: str) -> dict:
        return {
            "sub": "550e8400-e29b-41d4-a716-446655440000",
            "email": "ecc@example.com",
            "role": "authenticated",
            "email_verified": True,
        }

    monkeypatch.setattr("app.core.supabase_auth._decode_with_jwks", fake_jwks)
    claims = verify_supabase_access_token(_unsigned_header_token("ES256"))
    assert claims["email"] == "ecc@example.com"