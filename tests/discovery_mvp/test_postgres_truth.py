"""Required PostgreSQL certification. Skip is a failure when required."""

from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, inspect, text

from app.database import Base
import app.models  # noqa: F401
from app.models.discovery import DiscoveryEvidenceGap, DiscoveryFinding


def _postgres_url() -> str | None:
    for key in ("HERBAGRAPH_TEST_POSTGRES", "DATABASE_URL"):
        value = os.environ.get(key) or ""
        if "postgres" in value.lower():
            return value.replace("postgresql+asyncpg://", "postgresql://")
    return None


def _require_or_skip() -> str:
    url = _postgres_url()
    if url is None:
        if os.environ.get("HERBAGRAPH_REQUIRE_POSTGRES") == "1":
            pytest.fail("PostgreSQL URL required; skip is not allowed on a truth-layer PR")
        pytest.skip("PostgreSQL URL not provided")
    return url


@pytest.mark.requires_postgres
def test_orm_constraints_exist_in_live_postgres():
    url = _require_or_skip()
    engine = create_engine(url)
    schema = f"orm_{uuid.uuid4().hex[:10]}"
    try:
        with engine.begin() as conn:
            conn.execute(text(f"CREATE SCHEMA {schema}"))
            conn.execute(text(f"SET search_path TO {schema}"))
            Base.metadata.create_all(bind=conn)
        inspector = inspect(engine)
        fks = inspector.get_foreign_keys("discovery_findings", schema=schema)
        assert any(
            "supersedes_finding_id" in (item.get("constrained_columns") or [])
            and item.get("referred_table") == "discovery_findings"
            for item in fks
        ), "live postgres missing supersedes self-FK"
        indexes = inspector.get_indexes("discovery_evidence_gaps", schema=schema)
        names = {item.get("name") for item in indexes}
        assert "uq_discovery_gaps_active_code" in names or "uq_discovery_gaps_identity" in names
        assert DiscoveryFinding.__table__.c.supersedes_finding_id.foreign_keys
        assert any(index.name == "uq_discovery_gaps_active_code" for index in DiscoveryEvidenceGap.__table__.indexes)
    finally:
        with engine.begin() as conn:
            conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        engine.dispose()
