"""DI-06 uniqueness and concurrent-writer definitions.

Claim status: scaffolded. PR-A has no migration or concurrent-writer harness.
These tests skip even when DATABASE_URL points at PostgreSQL. PR-C must
replace the skip with observed database evidence.
"""

from __future__ import annotations

import pytest

from tests.discovery_mvp.red import SCAFFOLDED

pytestmark = pytest.mark.requires_postgres

_SKIP = pytest.mark.skip(
    reason=(
        f"{SCAFFOLDED}: PR-A defines the PostgreSQL claims but has no migration or "
        "concurrent-writer harness; PR-C must replace this skip with real database evidence"
    )
)


@_SKIP
def test_postgres_unique_active_finding_identity():
    """Two inserts of the same finding identity cannot both remain active.

    Identity (ADR-MVP-003): case + normalized concept + normalized value + source event/turn.
    Active uniqueness is a separate partial unique index, not part of identity.
    """
    raise AssertionError("unreachable until PR-C provides a real PostgreSQL uniqueness test")


@_SKIP
def test_postgres_concurrent_writers_cannot_duplicate_active_identity():
    """Two concurrent workers inserting the same identity must yield one active row.

    Read-then-insert is not sufficient. Require ON CONFLICT / unique violation handling.
    """
    raise AssertionError("unreachable until PR-C provides a real concurrent-writer harness")
