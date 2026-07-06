"""add lab processing and report generation stages

Revision ID: d8f2a1b3c4e5
Revises: c170693719b3
Create Date: 2026-07-06 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import app.models.mixins

# revision identifiers, used by Alembic.
revision: str = "d8f2a1b3c4e5"
down_revision: Union[str, None] = "c170693719b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "lab_reports",
        sa.Column("processing_stage", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "lab_reports",
        sa.Column("report_stage", sa.String(length=30), nullable=True),
    )
    op.add_column(
        "lab_reports",
        sa.Column("report_error_message", sa.Text(), nullable=True),
    )
    op.add_column(
        "lab_reports",
        sa.Column("latest_report_id", app.models.mixins.GUID(length=36), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("lab_reports", "latest_report_id")
    op.drop_column("lab_reports", "report_error_message")
    op.drop_column("lab_reports", "report_stage")
    op.drop_column("lab_reports", "processing_stage")