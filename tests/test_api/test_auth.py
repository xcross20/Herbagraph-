import pytest

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# register
# ---------------------------------------------------------------------------


async def test_register_happy_path(client):
    resp = await client.post(
        "/api/v1/auth/register", json={"email": "newuser@example.com", "password": "SecurePass1"}
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["email"] == "newuser@example.com"
    assert body["is_active"] is True
    assert body["is_verified"] is False
    assert "id" in body
    assert "created_at" in body
    assert "password" not in body
    assert "hashed_password" not in body


async def test_register_duplicate_email_returns_409(client):
    payload = {"email": "dupe@example.com", "password": "SecurePass1"}
    first = await client.post("/api/v1/auth/register", json=payload)
    assert first.status_code == 201

    second = await client.post("/api/v1/auth/register", json=payload)
    assert second.status_code == 409
    assert "already registered" in second.json()["detail"].lower()


@pytest.mark.parametrize(
    "password",
    [
        "Short1",  # too short (6 chars)
        "nouppercase1",  # no uppercase
        "NoDigitsHere",  # no digit
    ],
)
async def test_register_weak_password_returns_422(client, password):
    resp = await client.post(
        "/api/v1/auth/register", json={"email": "weakpw@example.com", "password": password}
    )
    assert resp.status_code == 422


async def test_register_too_short_password_message(client):
    resp = await client.post(
        "/api/v1/auth/register", json={"email": "shortpw@example.com", "password": "Ab1"}
    )
    assert resp.status_code == 422
    detail = str(resp.json()["detail"])
    assert "at least 8 characters" in detail


async def test_register_no_uppercase_password_message(client):
    resp = await client.post(
        "/api/v1/auth/register", json={"email": "nouppw@example.com", "password": "lowercase1"}
    )
    assert resp.status_code == 422
    detail = str(resp.json()["detail"])
    assert "uppercase" in detail


async def test_register_no_digit_password_message(client):
    resp = await client.post(
        "/api/v1/auth/register", json={"email": "nodigitpw@example.com", "password": "NoDigitsHere"}
    )
    assert resp.status_code == 422
    detail = str(resp.json()["detail"])
    assert "digit" in detail


async def test_register_invalid_email_returns_422(client):
    resp = await client.post(
        "/api/v1/auth/register", json={"email": "not-an-email", "password": "SecurePass1"}
    )
    assert resp.status_code == 422


async def test_register_missing_email_field_returns_422(client):
    resp = await client.post("/api/v1/auth/register", json={"password": "SecurePass1"})
    assert resp.status_code == 422


async def test_register_boundary_8_char_valid_password_succeeds(client):
    resp = await client.post(
        "/api/v1/auth/register", json={"email": "boundary@example.com", "password": "Abcdefg1"}
    )
    assert resp.status_code == 201, resp.text


async def test_register_frees_up_email_after_deletion(client):
    payload = {"email": "reusable@example.com", "password": "SecurePass1"}
    first = await client.post("/api/v1/auth/register", json=payload)
    assert first.status_code == 201

    login_resp = await client.post("/api/v1/auth/login", json=payload)
    token = login_resp.json()["access_token"]
    delete_resp = await client.delete(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert delete_resp.status_code == 204

    second = await client.post("/api/v1/auth/register", json=payload)
    assert second.status_code == 201


# ---------------------------------------------------------------------------
# login
# ---------------------------------------------------------------------------


async def test_login_happy_path(client):
    await client.post(
        "/api/v1/auth/register", json={"email": "loginuser@example.com", "password": "SecurePass1"}
    )
    resp = await client.post(
        "/api/v1/auth/login", json={"email": "loginuser@example.com", "password": "SecurePass1"}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert "access_token" in body and body["access_token"]
    assert "refresh_token" in body and body["refresh_token"]


async def test_refresh_token_returns_new_access_token(client):
    await client.post(
        "/api/v1/auth/register", json={"email": "refreshuser@example.com", "password": "SecurePass1"}
    )
    login_resp = await client.post(
        "/api/v1/auth/login", json={"email": "refreshuser@example.com", "password": "SecurePass1"}
    )
    refresh_token = login_resp.json()["refresh_token"]
    old_access = login_resp.json()["access_token"]

    refresh_resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_resp.status_code == 200, refresh_resp.text
    body = refresh_resp.json()
    assert body["access_token"]
    assert body["refresh_token"]

    me_resp = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"}
    )
    assert old_access  # issued at login; refresh should return a usable replacement
    assert me_resp.status_code == 200


async def test_refresh_token_invalid_returns_401(client):
    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": "not-a-real-token"})
    assert resp.status_code == 401


async def test_login_wrong_password_returns_401(client):
    await client.post(
        "/api/v1/auth/register", json={"email": "wrongpw@example.com", "password": "SecurePass1"}
    )
    resp = await client.post(
        "/api/v1/auth/login", json={"email": "wrongpw@example.com", "password": "WrongPass1"}
    )
    assert resp.status_code == 401
    assert "incorrect" in resp.json()["detail"].lower()


async def test_login_nonexistent_email_returns_401(client):
    resp = await client.post(
        "/api/v1/auth/login", json={"email": "nobody@example.com", "password": "SecurePass1"}
    )
    assert resp.status_code == 401
    assert "incorrect" in resp.json()["detail"].lower()


async def test_login_missing_password_field_returns_422(client):
    resp = await client.post("/api/v1/auth/login", json={"email": "nobody@example.com"})
    assert resp.status_code == 422


async def test_login_response_token_type_is_bearer(client):
    await client.post(
        "/api/v1/auth/register", json={"email": "bearer-check@example.com", "password": "SecurePass1"}
    )
    resp = await client.post(
        "/api/v1/auth/login", json={"email": "bearer-check@example.com", "password": "SecurePass1"}
    )
    assert resp.json()["token_type"] == "bearer"


# ---------------------------------------------------------------------------
# me
# ---------------------------------------------------------------------------


async def test_get_me_requires_auth(client):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


async def test_get_me_with_invalid_token_returns_401(client):
    resp = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401


async def test_get_me_with_malformed_auth_header_returns_401(client, auth_headers):
    token = auth_headers["Authorization"].split(" ", 1)[1]
    # Missing the "Bearer " scheme prefix entirely.
    resp = await client.get("/api/v1/auth/me", headers={"Authorization": token})
    assert resp.status_code == 401


async def test_get_me_with_refresh_token_rejected(client):
    from app.core.security import create_refresh_token

    register_resp = await client.post(
        "/api/v1/auth/register", json={"email": "refresh-me@example.com", "password": "SecurePass1"}
    )
    user_id = register_resp.json()["id"]
    refresh_token = create_refresh_token(user_id)
    resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {refresh_token}"})
    assert resp.status_code == 401


async def test_get_me_returns_correct_user(authed_client, test_user):
    resp = await authed_client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(test_user.id)
    assert body["email"] == test_user.email


async def test_delete_me_removes_user(authed_client):
    resp = await authed_client.delete("/api/v1/auth/me")
    assert resp.status_code == 204

    # Subsequent requests with the same token should now fail: the user is gone.
    me_resp = await authed_client.get("/api/v1/auth/me")
    assert me_resp.status_code == 401


async def test_delete_me_requires_auth(client):
    resp = await client.delete("/api/v1/auth/me")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# profile
# ---------------------------------------------------------------------------


async def test_get_profile_requires_auth(client):
    resp = await client.get("/api/v1/auth/profile")
    assert resp.status_code == 401


async def test_get_profile_happy_path(authed_client):
    resp = await authed_client.get("/api/v1/auth/profile")
    assert resp.status_code == 200
    body = resp.json()
    assert body["age_range"] is None
    assert body["biological_sex"] is None
    assert body["health_goals"] == []
    assert body["current_medications"] == []
    assert body["current_supplements"] == []
    assert body["known_conditions"] == []


async def test_put_profile_requires_auth(client):
    resp = await client.put("/api/v1/auth/profile", json={"age_range": "30-39"})
    assert resp.status_code == 401


async def test_put_profile_happy_path(authed_client):
    payload = {
        "age_range": "30-39",
        "biological_sex": "female",
        "health_goals": ["longevity", "energy"],
        "current_medications": ["metformin"],
        "current_supplements": ["vitamin d"],
        "known_conditions": ["prediabetes"],
    }
    resp = await authed_client.put("/api/v1/auth/profile", json=payload)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["age_range"] == "30-39"
    assert body["biological_sex"] == "female"
    assert body["health_goals"] == ["longevity", "energy"]
    assert body["current_medications"] == ["metformin"]
    assert body["current_supplements"] == ["vitamin d"]
    assert body["known_conditions"] == ["prediabetes"]

    # Verify the update persisted.
    get_resp = await authed_client.get("/api/v1/auth/profile")
    assert get_resp.json()["age_range"] == "30-39"


async def test_put_profile_partial_update_keeps_other_fields(authed_client):
    await authed_client.put("/api/v1/auth/profile", json={"age_range": "40-49"})
    resp = await authed_client.put("/api/v1/auth/profile", json={"biological_sex": "male"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["age_range"] == "40-49"
    assert body["biological_sex"] == "male"


# ---------------------------------------------------------------------------
# role / clinic_name (Phase 4: distinguishing individual vs. clinician accounts)
# ---------------------------------------------------------------------------


async def test_register_defaults_to_individual_role(client):
    resp = await client.post(
        "/api/v1/auth/register", json={"email": "solo@example.com", "password": "SecurePass1"}
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["role"] == "individual"
    assert body["clinic_name"] is None


async def test_register_as_clinician_with_clinic_name(client):
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "doc@example.com",
            "password": "SecurePass1",
            "role": "clinician",
            "clinic_name": "Riverside Wellness Clinic",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["role"] == "clinician"
    assert body["clinic_name"] == "Riverside Wellness Clinic"


async def test_register_rejects_invalid_role(client):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "bad@example.com", "password": "SecurePass1", "role": "superadmin"},
    )
    assert resp.status_code == 422


async def test_verify_signup_access_rejects_wrong_code(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "signup_access_code", "19922026")
    resp = await client.post(
        "/api/v1/auth/verify-signup-access",
        json={"email": "preview@example.com", "access_code": "wrong"},
    )
    assert resp.status_code == 403


async def test_register_requires_access_code_when_enabled(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "signup_access_code", "19922026")
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "gated@example.com", "password": "SecurePass1"},
    )
    assert resp.status_code == 403


async def test_auth_config_includes_google_oauth_flag(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "google_oauth_enabled", True)
    monkeypatch.setattr(settings, "auth_provider", "local")
    resp = await client.get("/api/v1/auth/config")
    assert resp.status_code == 200
    assert resp.json()["google_oauth_enabled"] is False

    monkeypatch.setattr(settings, "auth_provider", "supabase")
    monkeypatch.setattr(settings, "supabase_url", "https://example.supabase.co")
    monkeypatch.setattr(settings, "supabase_anon_key", "test-anon-key")
    resp2 = await client.get("/api/v1/auth/config")
    assert resp2.status_code == 200
    assert resp2.json()["google_oauth_enabled"] is True


async def test_verify_access_code_issues_oauth_approval_token(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "signup_access_code", "19922026")
    resp = await client.post(
        "/api/v1/auth/verify-access-code",
        json={"access_code": "19922026"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["approval_token"]
    assert body["expires_in"] == 900


async def test_verify_access_code_rejects_invalid_code(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "signup_access_code", "19922026")
    resp = await client.post(
        "/api/v1/auth/verify-access-code",
        json={"access_code": "nope"},
    )
    assert resp.status_code == 403


async def test_register_succeeds_after_access_code_verified(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "signup_access_code", "19922026")
    verify = await client.post(
        "/api/v1/auth/verify-signup-access",
        json={"email": "gated@example.com", "access_code": "19922026"},
    )
    assert verify.status_code == 204
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "gated@example.com", "password": "SecurePass1"},
    )
    assert resp.status_code == 201, resp.text
