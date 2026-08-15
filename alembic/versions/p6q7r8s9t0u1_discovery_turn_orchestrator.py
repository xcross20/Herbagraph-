"""Turn orchestrator columns on cases and turns.

Revision ID: p6q7r8s9t0u1
Revises: o5p6q7r8s9t0
Create Date: 2026-08-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "p6q7r8s9t0u1"
down_revision = "o5p6q7r8s9t0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("discovery_cases", sa.Column("stage", sa.String(length=40), nullable=False, server_default="opening"))
    op.add_column("discovery_cases", sa.Column("problem_representation", sa.Text(), nullable=True))
    op.add_column("discovery_turns", sa.Column("intent", sa.String(length=80), nullable=True))
    op.add_column("discovery_turns", sa.Column("action_type", sa.String(length=40), nullable=True))
    op.add_column("discovery_turns", sa.Column("stage", sa.String(length=40), nullable=True))
    op.add_column("discovery_turns", sa.Column("payload", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("discovery_turns", "payload")
    op.drop_column("discovery_turns", "stage")
    op.drop_column("discovery_turns", "action_type")
    op.drop_column("discovery_turns", "intent")
    op.drop_column("discovery_cases", "problem_representation")
    op.drop_column("discovery_cases", "stage")
