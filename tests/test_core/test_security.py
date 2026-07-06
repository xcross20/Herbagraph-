from datetime import timedelta

import pytest
from jose import jwt

from app.config import settings
from app.core import security
from app.core.security import (
    InvalidTokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

pytestmark = pytest.mark.unit


class TestHashPassword:
    def test_hash_is_not_plaintext(self):
        hashed = hash_password("correct horse battery staple")
        assert hashed != "correct horse battery staple"

    def test_hash_roundtrip_verifies_true(self):
        hashed = hash_password("s3cr3t-P@ssw0rd")
        assert verify_password("s3cr3t-P@ssw0rd", hashed) is True

    def test_wrong_password_fails_verification(self):
        hashed = hash_password("the-real-password")
        assert verify_password("not-the-real-password", hashed) is False

    def test_hashing_same_password_twice_gives_different_hashes(self):
        # bcrypt salts each hash, so two hashes of the same password should differ.
        h1 = hash_password("same-password")
        h2 = hash_password("same-password")
        assert h1 != h2
        assert verify_password("same-password", h1) is True
        assert verify_password("same-password", h2) is True

    def test_empty_password_can_be_hashed_and_verified(self):
        hashed = hash_password("")
        assert verify_password("", hashed) is True
        assert verify_password("nonempty", hashed) is False


class TestCreateAndDecodeTokens:
    def test_access_token_decodes_to_correct_subject(self):
        token = create_access_token("user-123")
        subject = decode_token(token, expected_type="access")
        assert subject == "user-123"

    def test_refresh_token_decodes_to_correct_subject(self):
        token = create_refresh_token("user-456")
        subject = decode_token(token, expected_type="refresh")
        assert subject == "user-456"

    def test_access_token_decoded_as_refresh_raises(self):
        token = create_access_token("user-123")
        with pytest.raises(InvalidTokenError):
            decode_token(token, expected_type="refresh")

    def test_refresh_token_decoded_as_access_raises(self):
        token = create_refresh_token("user-123")
        with pytest.raises(InvalidTokenError):
            decode_token(token, expected_type="access")

    def test_default_expected_type_is_access(self):
        token = create_access_token("user-789")
        # decode_token's default expected_type is "access", so calling with no
        # second arg on an access token should succeed.
        assert decode_token(token) == "user-789"

    def test_tampered_token_raises_invalid_token_error(self):
        token = create_access_token("user-123")
        tampered = token[:-4] + ("A" * 4 if token[-4:] != "A" * 4 else "B" * 4)
        with pytest.raises(InvalidTokenError):
            decode_token(tampered)

    def test_garbage_token_raises_invalid_token_error(self):
        with pytest.raises(InvalidTokenError):
            decode_token("this-is-not-a-jwt-at-all")

    def test_token_signed_with_wrong_secret_raises(self):
        bad_payload = {"sub": "user-123", "type": "access"}
        bad_token = jwt.encode(bad_payload, "a-completely-different-secret", algorithm=settings.algorithm)
        with pytest.raises(InvalidTokenError):
            decode_token(bad_token)

    def test_expired_token_raises_invalid_token_error(self):
        expired_token = security._create_token("user-123", timedelta(seconds=-1), "access")
        with pytest.raises(InvalidTokenError):
            decode_token(expired_token)

    def test_token_missing_subject_raises(self):
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        payload = {"type": "access", "iat": now, "exp": now + timedelta(minutes=5)}
        token = jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)
        with pytest.raises(InvalidTokenError):
            decode_token(token, expected_type="access")

    def test_token_missing_type_raises(self):
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        payload = {"sub": "user-123", "iat": now, "exp": now + timedelta(minutes=5)}
        token = jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)
        with pytest.raises(InvalidTokenError):
            decode_token(token, expected_type="access")

    def test_different_subjects_produce_different_tokens(self):
        token_a = create_access_token("user-a")
        token_b = create_access_token("user-b")
        assert token_a != token_b
