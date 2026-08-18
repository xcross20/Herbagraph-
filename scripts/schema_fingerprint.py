"""Compare live PostgreSQL tables to SQLAlchemy metadata."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import Base  # noqa: E402
import app.models  # noqa: E402,F401


REQUIRED = (
    "discovery_cases",
    "discovery_findings",
    "discovery_hypotheses",
    "discovery_evidence_gaps",
    "discovery_investigation_branches",
)


def _sync_url(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://")


def fingerprint(engine) -> dict:
    inspector = inspect(engine)
    tables = sorted(inspector.get_table_names())
    orm = sorted(Base.metadata.tables)
    return {
        "live_tables": tables,
        "orm_tables": orm,
        "missing_from_live": sorted(set(REQUIRED) - set(tables)),
        "digest": hashlib.sha256("\n".join(tables).encode()).hexdigest(),
    }


def main() -> int:
    url = os.environ.get("HERBAGRAPH_TEST_POSTGRES") or os.environ.get("DATABASE_URL") or ""
    if "postgres" not in url.lower():
        print("postgres url required", file=sys.stderr)
        return 1
    engine = create_engine(_sync_url(url))
    try:
        payload = fingerprint(engine)
    finally:
        engine.dispose()
    print(json.dumps(payload, indent=2, sort_keys=True))
    if payload["missing_from_live"]:
        print("required discovery tables missing", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
