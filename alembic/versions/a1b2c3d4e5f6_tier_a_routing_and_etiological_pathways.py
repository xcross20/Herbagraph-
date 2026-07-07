"""Tier A routing: pathway_type and recommendation_intent columns.

Revision ID: a1b2c3d4e5f6
Revises: f2b3c4d5e6f7
Create Date: 2026-07-06
"""

from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "f2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pathways",
        sa.Column("pathway_type", sa.String(length=20), nullable=False, server_default="signaling"),
    )
    op.add_column(
        "evidence_claims",
        sa.Column("recommendation_intent", sa.String(length=30), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("evidence_claims", "recommendation_intent")
    op.drop_column("pathways", "pathway_type")