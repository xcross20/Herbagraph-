"""Add durable turn idempotency key.

Revision ID: u4b5c6d7e8f9
Revises: u3a4b5c6d7e8
Create Date: 2026-08-18
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "u4b5c6d7e8f9"
down_revision = "u3a4b5c6d7e8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("discovery_turns", sa.Column("idempotency_key", sa.String(length=80), nullable=True))
    op.create_index(
        "uq_discovery_turns_idempotency",
        "discovery_turns",
        ["case_id", "idempotency_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_discovery_turns_idempotency", table_name="discovery_turns")
    op.drop_column("discovery_turns", "idempotency_key")
