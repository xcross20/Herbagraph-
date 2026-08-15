"""Append-only Investigation Map versions.

Revision ID: q7r8s9t0u1v2
Revises: p6q7r8s9t0u1
Create Date: 2026-08-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "q7r8s9t0u1v2"
down_revision = "p6q7r8s9t0u1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "discovery_map_versions",
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("case_id", sa.CHAR(length=36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("fingerprint", sa.String(length=32), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["discovery_cases.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_discovery_map_versions_case_id", "discovery_map_versions", ["case_id"])


def downgrade() -> None:
    op.drop_index("ix_discovery_map_versions_case_id", table_name="discovery_map_versions")
    op.drop_table("discovery_map_versions")
