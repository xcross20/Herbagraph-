"""Discovery-recommended tests live in the existing patient portal.

Revision ID: r8s9t0u1v2w3
Revises: q7r8s9t0u1v2
Create Date: 2026-08-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "r8s9t0u1v2w3"
down_revision = "q7r8s9t0u1v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "discovery_test_plan_items",
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("user_id", sa.CHAR(length=36), nullable=False),
        sa.Column("case_id", sa.CHAR(length=36), nullable=False),
        sa.Column("patient_id", sa.CHAR(length=36), nullable=True),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["case_id"], ["discovery_cases.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_discovery_test_plan_items_user_id", "discovery_test_plan_items", ["user_id"])
    op.create_index("ix_discovery_test_plan_items_case_id", "discovery_test_plan_items", ["case_id"])
    op.create_index("ix_discovery_test_plan_items_patient_id", "discovery_test_plan_items", ["patient_id"])


def downgrade() -> None:
    op.drop_index("ix_discovery_test_plan_items_patient_id", table_name="discovery_test_plan_items")
    op.drop_index("ix_discovery_test_plan_items_case_id", table_name="discovery_test_plan_items")
    op.drop_index("ix_discovery_test_plan_items_user_id", table_name="discovery_test_plan_items")
    op.drop_table("discovery_test_plan_items")
