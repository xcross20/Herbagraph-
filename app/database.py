from collections.abc import AsyncGenerator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


def _to_sync_url(url: str) -> str:
    """Derive a synchronous driver URL (used by Celery workers) from the async DATABASE_URL."""
    return url.replace("+asyncpg", "").replace("+aiosqlite", "")


engine = create_async_engine(settings.database_url, echo=settings.debug, future=True)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

# Celery workers use a plain synchronous session so tasks never need an event loop of their own.
# Built lazily so importing this module never requires a sync DBAPI driver (e.g. psycopg2) to be
# installed unless a Celery task actually runs.
_sync_engine = None
_SyncSessionLocal: sessionmaker | None = None


def get_sync_session_factory() -> sessionmaker:
    global _sync_engine, _SyncSessionLocal
    if _SyncSessionLocal is None:
        _sync_engine = create_engine(_to_sync_url(settings.database_url), echo=settings.debug, future=True)
        _SyncSessionLocal = sessionmaker(bind=_sync_engine, autoflush=False, expire_on_commit=False)
    return _SyncSessionLocal


def get_sync_db() -> Session:
    return get_sync_session_factory()()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
