"""Persist Case safety JSON. Turn kind stays 20 chars; full action is action_type.

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


def downgrade() -> None:
    op.drop_column("discovery_cases", "safety_json")
