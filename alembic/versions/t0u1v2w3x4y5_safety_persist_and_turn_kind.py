"""Persist Case safety JSON and widen discovery turn kinds.

Revision ID: t0u1v2w3x4y5
Revises: s9t0u1v2w3x4
Create Date: 2026-08-15
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "t0u1v2w3x4y5"
down_revision = "s9t0u1v2w3x4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("discovery_cases", sa.Column("safety_json", sa.Text(), nullable=True))
    with op.batch_alter_table("discovery_turns") as batch:
        batch.alter_column("kind", existing_type=sa.String(length=20), type_=sa.String(length=40))


def downgrade() -> None:
    with op.batch_alter_table("discovery_turns") as batch:
        batch.alter_column("kind", existing_type=sa.String(length=40), type_=sa.String(length=20))
    op.drop_column("discovery_cases", "safety_json")
