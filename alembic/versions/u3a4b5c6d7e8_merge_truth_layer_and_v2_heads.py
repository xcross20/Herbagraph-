"""Merge truth-layer and investigation-state-v2 Alembic heads.

Revision ID: u3a4b5c6d7e8
Revises: u1v2w3x4y5z6, u2v3w4x5y6z8
Create Date: 2026-08-18

Empty merge. Does not replay either branch's DDL. Production/UAT that already
ran one branch can stamp forward. The truth-layer CI rehearsal upgrades
explicitly to u2v3w4x5y6z8 and does not use this head.
"""

from __future__ import annotations

revision = "u3a4b5c6d7e8"
down_revision = ("u1v2w3x4y5z6", "u2v3w4x5y6z8")
branch_labels = None
depends_on = None


def upgrade() -> None:
    return


def downgrade() -> None:
    return
