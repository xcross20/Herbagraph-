"""Admin user management API tests."""

import uuid

import pytest
from sqlalchemy import select

from app.core.security import create_access_token, hash_password
from app.models.user import HealthProfile, User

pytestmark = pytest.mark.asyncio


@pytest.fixture
def admin_headers(test_user, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", test_user.email)
    from app.config import get_settings

    get_settings.cache_clear()
    token = create_access_token(str(test_user.id))
    yield {"Authorization": f"Bearer {token}"}
    get_settings.cache_clear()
    monkeypatch.delenv("ADMIN_EMAILS", raising=False)


async def _second_user(db_session):
    user = User(
        email=f"other-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=hash_password("OtherPass1"),
        is_active=True,
        is_verified=False,
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(HealthProfile(user_id=user.id))
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def test_list_users_requires_admin(client):
    response = await client.get("/api/v1/admin/users")
    assert response.status_code in (401, 403)


async def test_admin_can_list_and_update_user(admin_headers, client, db_session, test_user):
    other = await _second_user(db_session)
    client.headers.update(admin_headers)

    listed = await client.get("/api/v1/admin/users")
    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] >= 2
    emails = {row["email"] for row in body["items"]}
    assert other.email in emails

    updated = await client.patch(
        f"/api/v1/admin/users/{other.id}",
        json={"is_verified": True, "role": "clinician", "full_name": "Dr. Test"},
    )
    assert updated.status_code == 200
    row = updated.json()
    assert row["is_verified"] is True
    assert row["role"] == "clinician"
    assert row["full_name"] == "Dr. Test"


async def test_admin_can_deactivate_and_delete_user(admin_headers, client, db_session):
    other = await _second_user(db_session)
    client.headers.update(admin_headers)

    deactivated = await client.patch(f"/api/v1/admin/users/{other.id}", json={"is_active": False})
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False

    deleted = await client.delete(f"/api/v1/admin/users/{other.id}")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True

    result = await db_session.execute(select(User).where(User.id == other.id))
    assert result.scalar_one_or_none() is None


async def test_admin_cannot_delete_self(admin_headers, client, test_user):
    client.headers.update(admin_headers)
    response = await client.delete(f"/api/v1/admin/users/{test_user.id}")
    assert response.status_code == 400