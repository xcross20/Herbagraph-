"""Additive Case control state for the usefulness governor.

Revision ID: u7e8f9g0h1i2
Revises: u6d7e8f9g0h1
Create Date: 2026-08-18
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "u7e8f9g0h1i2"
down_revision = "u6d7e8f9g0h1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("discovery_cases", sa.Column("control_json", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("discovery_cases", "control_json")
