"""Empty-db and upgrade-from-previous Alembic rehearsals against PostgreSQL."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text


def _sync_url(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://")


def _cfg() -> Config:
    return Config(str(Path("alembic.ini")))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("empty", "upgrade"), required=True)
    args = parser.parse_args()
    url = os.environ.get("HERBAGRAPH_TEST_POSTGRES") or os.environ.get("DATABASE_URL")
    if not url or "postgres" not in url.lower():
        print("postgres url required", file=sys.stderr)
        return 1
    sync = _sync_url(url)
    os.environ["DATABASE_URL"] = url if "+asyncpg" in url else url.replace("postgresql://", "postgresql+asyncpg://")
    engine = create_engine(sync)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    if args.mode == "empty":
        command.upgrade(_cfg(), "head")
    else:
        command.upgrade(_cfg(), "u1v2w3x4y5z7")
        command.upgrade(_cfg(), "head")
        command.downgrade(_cfg(), "u1v2w3x4y5z7")
        command.upgrade(_cfg(), "head")
    print(f"{args.mode} migration rehearsal ok")
    engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
