import os
import tempfile

from cryptography.fernet import Fernet

# These must be set before *any* `app.*` module is imported anywhere in the test session,
# since app.config.settings is a module-level singleton read once at import time.
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production-0123456789")
os.environ.setdefault("ENCRYPTION_KEY", Fernet.generate_key().decode())
os.environ.setdefault("ANTHROPIC_API_KEY", "test-anthropic-api-key")
os.environ.setdefault("NCBI_EMAIL", "test@herbagraph.io")
os.environ.setdefault("UPLOAD_DIR", tempfile.mkdtemp(prefix="herbagraph-test-uploads-"))
os.environ.setdefault("DEBUG", "false")

import uuid  # noqa: E402

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app import database  # noqa: E402
from app.api.deps import get_db  # noqa: E402
from app.core.security import create_access_token  # noqa: E402
from app.database import Base  # noqa: E402
from app.knowledge_graph.seeder import seed_knowledge_graph  # noqa: E402
from app.main import app  # noqa: E402
from app.models.user import HealthProfile, User  # noqa: E402
from app.workers.celery_app import celery_app  # noqa: E402

celery_app.conf.task_always_eager = True
celery_app.conf.task_eager_propagates = True


@pytest_asyncio.fixture
async def db_session(tmp_path, monkeypatch):
    """A fresh file-backed SQLite DB per test, shared between the async app engine and the
    sync engine Celery tasks use, so API-triggered background tasks see consistent data."""
    db_path = tmp_path / "test.db"
    async_url = f"sqlite+aiosqlite:///{db_path}"
    sync_url = f"sqlite:///{db_path}"

    test_engine = create_async_engine(async_url, future=True)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    test_session_factory = async_sessionmaker(bind=test_engine, expire_on_commit=False, autoflush=False)

    sync_engine = create_engine(sync_url, future=True)
    sync_session_factory = sessionmaker(bind=sync_engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(database, "get_sync_session_factory", lambda: sync_session_factory)

    async with test_session_factory() as session:
        yield session

    await test_engine.dispose()
    sync_engine.dispose()


@pytest_asyncio.fixture
async def client(db_session):
    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_user(db_session):
    user = User(
        email=f"user-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="not-a-real-hash",
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(HealthProfile(user_id=user.id))
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user):
    token = create_access_token(str(test_user.id))
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def authed_client(client, auth_headers):
    client.headers.update(auth_headers)
    return client


@pytest_asyncio.fixture
async def seeded_db(db_session):
    await seed_knowledge_graph(db_session)
    return db_session
