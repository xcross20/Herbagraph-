"""Add monitoring causal taxonomy.

Revision ID: u6d7e8f9g0h1
Revises: u5c6d7e8f9g0
Create Date: 2026-08-18
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "u6d7e8f9g0h1"
down_revision = "u5c6d7e8f9g0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "discovery_monitoring_events",
        sa.Column(
            "causal_kind",
            sa.String(length=40),
            nullable=False,
            server_default="insufficient_for_causal_inference",
        ),
    )


def downgrade() -> None:
    op.drop_column("discovery_monitoring_events", "causal_kind")
