"""DI-06 uniqueness and concurrent-writer definitions.

Claim status: scaffolded. SQLite cannot substantiate these claims.
They do not need to pass in PR-A. Run against PostgreSQL in PR-C.
"""

from __future__ import annotations

import os

import pytest

from tests.discovery_mvp.red import SCAFFOLDED

pytestmark = pytest.mark.requires_postgres

_POSTGRES = "postgres" in (os.environ.get("DATABASE_URL") or "").lower()
_SKIP = pytest.mark.skipif(
    not _POSTGRES,
    reason=f"{SCAFFOLDED}: SQLite cannot substantiate DI-06 uniqueness/concurrency",
)


@_SKIP
def test_postgres_unique_active_finding_identity():
    """Two inserts of the same finding identity cannot both remain active.

    Identity (ADR-MVP-003): case + normalized concept + normalized value + source event/turn.
    Active uniqueness is a separate partial unique index, not part of identity.
    """
    pytest.fail(
        f"{SCAFFOLDED}: PostgreSQL partial unique index not present on main; "
        "definition only until PR-C"
    )


@_SKIP
def test_postgres_concurrent_writers_cannot_duplicate_active_identity():
    """Two concurrent workers inserting the same identity must yield one active row.

    Read-then-insert is not sufficient. Require ON CONFLICT / unique violation handling.
    """
    pytest.fail(
        f"{SCAFFOLDED}: concurrent-writer harness not present on main; "
        "definition only until PR-C"
    )
