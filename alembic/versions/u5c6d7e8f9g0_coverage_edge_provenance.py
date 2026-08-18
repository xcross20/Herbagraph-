"""Persist coverage-rule provenance on evidence edges and prior branch closures.

Revision ID: u5c6d7e8f9g0
Revises: u4b5c6d7e8f9
Create Date: 2026-08-18
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "u5c6d7e8f9g0"
down_revision = "u4b5c6d7e8f9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "discovery_evidence_edges",
        sa.Column("coverage_relation", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "discovery_evidence_edges",
        sa.Column("rule_version", sa.String(length=80), nullable=True),
    )
    op.add_column("discovery_evidence_edges", sa.Column("rationale", sa.Text(), nullable=True))
    op.add_column(
        "discovery_evidence_edges",
        sa.Column("evaluated_at", sa.String(length=40), nullable=True),
    )
    op.add_column(
        "discovery_investigation_branches",
        sa.Column("prior_resolved_at", sa.String(length=40), nullable=True),
    )
    op.add_column(
        "discovery_investigation_branches",
        sa.Column("prior_close_reason", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("discovery_investigation_branches", "prior_close_reason")
    op.drop_column("discovery_investigation_branches", "prior_resolved_at")
    op.drop_column("discovery_evidence_edges", "evaluated_at")
    op.drop_column("discovery_evidence_edges", "rationale")
    op.drop_column("discovery_evidence_edges", "rule_version")
    op.drop_column("discovery_evidence_edges", "coverage_relation")
