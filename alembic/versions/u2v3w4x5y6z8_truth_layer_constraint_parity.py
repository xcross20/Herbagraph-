"""Forward-fix truth-layer ORM/migration parity.

Revision ID: u2v3w4x5y6z8
Revises: u1v2w3x4y5z7
Create Date: 2026-08-17

Preserves any UAT rows created after u1v2w3x4y5z7. Adds the missing
self-FK and the active-gap uniqueness constraint.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "u2v3w4x5y6z8"
down_revision = "u1v2w3x4y5z7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_foreign_key(
        "fk_discovery_findings_supersedes",
        "discovery_findings",
        "discovery_findings",
        ["supersedes_finding_id"],
        ["id"],
    )
    op.create_index(
        "uq_discovery_gaps_active_code",
        "discovery_evidence_gaps",
        ["case_id", "branch_code", "code"],
        unique=True,
        postgresql_where=sa.text("active IS true"),
        sqlite_where=sa.text("active = 1"),
    )


def downgrade() -> None:
    op.drop_index("uq_discovery_gaps_active_code", table_name="discovery_evidence_gaps")
    op.drop_constraint("fk_discovery_findings_supersedes", "discovery_findings", type_="foreignkey")
