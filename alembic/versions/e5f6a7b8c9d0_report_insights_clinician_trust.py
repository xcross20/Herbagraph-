"""Report insights — evidence summary, missing information, clinician trust sections

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-07-08
"""

from alembic import op
import sqlalchemy as sa

revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("recommendation_reports", sa.Column("report_insights", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("recommendation_reports", "report_insights")