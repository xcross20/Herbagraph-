#!/usr/bin/env python
"""Create the current SQLAlchemy schema on a non-production Railway database.

Historical Alembic revisions mix CHAR(36) GUID primary keys with later sa.Uuid()
foreign keys, so `alembic upgrade head` cannot apply to a fresh Postgres. UAT
and PR preview environments use this fallback, then stamp Alembic at head so
later additive revisions can apply. Refuses to run against production.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from app.core.runtime_env import is_production  # noqa: E402
from app.database import Base, engine  # noqa: E402
from app.models import *  # noqa: F401,F403,E402


def assert_not_production() -> None:
    if is_production():
        raise SystemExit("Refusing to bootstrap schema on production.")


def _alembic_config() -> Config:
    ini = Path(__file__).resolve().parent.parent / "alembic.ini"
    return Config(str(ini))


async def schema_ready() -> bool:
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = 'users' AND column_name = 'auth_provider' LIMIT 1"
            )
        )
        return result.first() is not None


async def rebuild_schema() -> None:
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        await conn.execute(text("GRANT ALL ON SCHEMA public TO CURRENT_USER"))
        await conn.execute(text("GRANT ALL ON SCHEMA public TO public"))
        await conn.run_sync(Base.metadata.create_all)


def stamp_head() -> None:
    command.stamp(_alembic_config(), "head")


async def main(*, force: bool) -> None:
    assert_not_production()
    if await schema_ready() and not force:
        print("Schema already has users.auth_provider; stamping Alembic head.")
        stamp_head()
        return
    print("Rebuilding non-production schema from SQLAlchemy models.")
    await rebuild_schema()
    stamp_head()
    print("Schema created and Alembic stamped at head.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--force",
        action="store_true",
        help="Drop and recreate even if users.auth_provider already exists.",
    )
    args = parser.parse_args()
    asyncio.run(main(force=args.force))
