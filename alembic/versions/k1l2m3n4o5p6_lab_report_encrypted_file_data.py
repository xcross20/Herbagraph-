"""Store encrypted lab file bytes in Postgres for multi-container deploys

Revision ID: k1l2m3n4o5p6
Revises: j0k1l2m3n4o5
Create Date: 2026-07-14
"""

from alembic import op
import sqlalchemy as sa

revision = "k1l2m3n4o5p6"
down_revision = "j0k1l2m3n4o5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("lab_reports", sa.Column("encrypted_file_data", sa.LargeBinary(), nullable=True))


def downgrade() -> None:
    op.drop_column("lab_reports", "encrypted_file_data")