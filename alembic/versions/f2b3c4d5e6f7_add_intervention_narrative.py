"""Add intervention_narrative to recommendations.

Revision ID: f2b3c4d5e6f7
Revises: e1a2b3c4d5e6
Create Date: 2026-07-06
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f2b3c4d5e6f7"
down_revision: Union[str, None] = "e1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("recommendations", sa.Column("intervention_narrative", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("recommendations", "intervention_narrative")