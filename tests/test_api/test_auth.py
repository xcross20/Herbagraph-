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


# ---------------------------------------------------------------------------
# me
# ---------------------------------------------------------------------------


async def test_get_me_requires_auth(client):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


async def test_get_me_with_invalid_token_returns_401(client):
    resp = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
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
