"""Truth-layer PostgreSQL migration rehearsal.

Does not replay the inherited historical Alembic chain (UUID vs CHAR
incompatibility on empty Postgres). Certifies current ORM schema and the
u1 → u2 truth-layer forward/rollback path.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from app.database import Base
import app.models  # noqa: F401


def _sync_url(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://")


def _cfg() -> Config:
    return Config(str(Path("alembic.ini")))


def _reset(engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))


def _has_fk(engine) -> bool:
    fks = inspect(engine).get_foreign_keys("discovery_findings")
    return any(
        "supersedes_finding_id" in (item.get("constrained_columns") or [])
        and item.get("referred_table") == "discovery_findings"
        for item in fks
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("empty", "upgrade"), required=True)
    args = parser.parse_args()
    url = os.environ.get("HERBAGRAPH_TEST_POSTGRES") or os.environ.get("DATABASE_URL")
    if not url or "postgres" not in url.lower():
        print("postgres url required", file=sys.stderr)
        return 1
    sync = _sync_url(url)
    os.environ["DATABASE_URL"] = (
        url if "+asyncpg" in url else url.replace("postgresql://", "postgresql+asyncpg://")
    )
    engine = create_engine(sync)
    try:
        _reset(engine)
        Base.metadata.create_all(engine)
        if not _has_fk(engine):
            print("empty create_all missing supersedes self-FK", file=sys.stderr)
            return 1
        if args.mode == "empty":
            print("empty-database current schema ok")
            return 0
        with engine.begin() as conn:
            for fk in inspect(engine).get_foreign_keys("discovery_findings"):
                if "supersedes_finding_id" in (fk.get("constrained_columns") or []) and fk.get("name"):
                    conn.execute(text(f'ALTER TABLE discovery_findings DROP CONSTRAINT IF EXISTS "{fk["name"]}"'))
            conn.execute(text("DROP INDEX IF EXISTS uq_discovery_gaps_active_code"))
        command.stamp(_cfg(), "u1v2w3x4y5z7")
        command.upgrade(_cfg(), "head")
        if not _has_fk(engine):
            print("upgrade head did not restore self-FK", file=sys.stderr)
            return 1
        command.downgrade(_cfg(), "u1v2w3x4y5z7")
        command.upgrade(_cfg(), "head")
        if not _has_fk(engine):
            print("forward-recovery did not restore self-FK", file=sys.stderr)
            return 1
        print("upgrade/rollback/forward-recovery rehearsal ok")
        return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
