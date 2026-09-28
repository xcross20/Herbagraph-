"""Public Stack Check rate buckets.

Revision ID: v8f9g0h1i2j3
Revises: u7e8f9g0h1i2
Create Date: 2026-09-28
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "v8f9g0h1i2j3"
down_revision = "u7e8f9g0h1i2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "public_rate_buckets",
        sa.Column("bucket_key", sa.String(length=200), primary_key=True),
        sa.Column("hit_count", sa.Integer(), nullable=False),
        sa.Column("window_started_epoch", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("public_rate_buckets")
