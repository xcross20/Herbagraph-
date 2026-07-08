"""Evidence Confidence & Explainability Engine columns

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-07-08
"""

from alembic import op
import sqlalchemy as sa

revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("recommendation_reports", sa.Column("report_versioning", sa.JSON(), nullable=True))
    op.add_column("recommendations", sa.Column("explainability", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("recommendations", "explainability")
    op.drop_column("recommendation_reports", "report_versioning")