"""Discovery outcomes and chat turns.

Revision ID: o5p6q7r8s9t0
Revises: n4o5p6q7r8s9
Create Date: 2026-08-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "o5p6q7r8s9t0"
down_revision = "n4o5p6q7r8s9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "discovery_outcomes",
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("case_id", sa.CHAR(length=36), nullable=False),
        sa.Column("hypothesis_code", sa.String(length=80), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("result", sa.Text(), nullable=True),
        sa.Column("question_code", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["discovery_cases.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_discovery_outcomes_case_id", "discovery_outcomes", ["case_id"])

    op.create_table(
        "discovery_turns",
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("case_id", sa.CHAR(length=36), nullable=False),
        sa.Column("role", sa.String(length=12), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("question_code", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["discovery_cases.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_discovery_turns_case_id", "discovery_turns", ["case_id"])


def downgrade() -> None:
    op.drop_index("ix_discovery_turns_case_id", table_name="discovery_turns")
    op.drop_table("discovery_turns")
    op.drop_index("ix_discovery_outcomes_case_id", table_name="discovery_outcomes")
    op.drop_table("discovery_outcomes")
