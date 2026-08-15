"""Longitudinal snapshots and case literature JSON.

Revision ID: s9t0u1v2w3x4
Revises: r8s9t0u1v2w3
Create Date: 2026-08-15
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "s9t0u1v2w3x4"
down_revision = "r8s9t0u1v2w3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("discovery_cases", sa.Column("literature_json", sa.Text(), nullable=True))
    op.create_table(
        "discovery_longitudinal_snapshots",
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("user_id", sa.CHAR(length=36), nullable=False),
        sa.Column("patient_id", sa.CHAR(length=36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_discovery_longitudinal_snapshots_user_id", "discovery_longitudinal_snapshots", ["user_id"])
    op.create_index("ix_discovery_longitudinal_snapshots_patient_id", "discovery_longitudinal_snapshots", ["patient_id"])


def downgrade() -> None:
    op.drop_index("ix_discovery_longitudinal_snapshots_patient_id", table_name="discovery_longitudinal_snapshots")
    op.drop_index("ix_discovery_longitudinal_snapshots_user_id", table_name="discovery_longitudinal_snapshots")
    op.drop_table("discovery_longitudinal_snapshots")
    op.drop_column("discovery_cases", "literature_json")
