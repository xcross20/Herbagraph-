"""Single Alembic head after archiving the unaccepted V2 sibling.

Revision ID: u3a4b5c6d7e8
Revises: u2v3w4x5y6z8
Create Date: 2026-08-18

The V2 investigation-state revision is archived and is not part of the
accepted upgrade path. Empty PostgreSQL uses `alembic upgrade head`.
"""

from __future__ import annotations

revision = "u3a4b5c6d7e8"
down_revision = "u2v3w4x5y6z8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    return


def downgrade() -> None:
    return
