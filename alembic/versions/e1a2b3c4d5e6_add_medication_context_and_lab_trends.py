"""Add medication_context and lab_trends to recommendation_reports.

Revision ID: e1a2b3c4d5e6
Revises: d8f2a1b3c4e5
Create Date: 2026-07-06
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e1a2b3c4d5e6"
down_revision: Union[str, None] = "d8f2a1b3c4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("recommendation_reports", sa.Column("medication_context", sa.JSON(), nullable=False, server_default="{}"))
    op.add_column("recommendation_reports", sa.Column("lab_trends", sa.JSON(), nullable=False, server_default="{}"))


def downgrade() -> None:
    op.drop_column("recommendation_reports", "lab_trends")
    op.drop_column("recommendation_reports", "medication_context")