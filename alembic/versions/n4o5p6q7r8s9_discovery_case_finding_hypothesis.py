"""Guided Discovery Case, Finding, and Hypothesis tables.

Revision ID: n4o5p6q7r8s9
Revises: m3n4o5p6q7r8
Create Date: 2026-08-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "n4o5p6q7r8s9"
down_revision = "m3n4o5p6q7r8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "discovery_cases",
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("user_id", sa.CHAR(length=36), nullable=False),
        sa.Column("patient_id", sa.CHAR(length=36), nullable=True),
        sa.Column("presenting_concern", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("lab_report_id", sa.CHAR(length=36), nullable=True),
        sa.Column("investigation_coverage", sa.Float(), nullable=False),
        sa.Column("snapshot", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["lab_report_id"], ["lab_reports.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_discovery_cases_user_id", "discovery_cases", ["user_id"])
    op.create_index("ix_discovery_cases_patient_id", "discovery_cases", ["patient_id"])

    op.create_table(
        "discovery_findings",
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("case_id", sa.CHAR(length=36), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=True),
        sa.Column("branch", sa.String(length=40), nullable=True),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["discovery_cases.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_discovery_findings_case_id", "discovery_findings", ["case_id"])

    op.create_table(
        "discovery_hypotheses",
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("case_id", sa.CHAR(length=36), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("branch", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("investigation_relevance", sa.Float(), nullable=False),
        sa.Column("diagnostic_certainty", sa.Float(), nullable=False),
        sa.Column("investigation_coverage", sa.Float(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("missing_markers", sa.Text(), nullable=True),
        sa.Column("investigations", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["discovery_cases.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_discovery_hypotheses_case_id", "discovery_hypotheses", ["case_id"])


def downgrade() -> None:
    op.drop_index("ix_discovery_hypotheses_case_id", table_name="discovery_hypotheses")
    op.drop_table("discovery_hypotheses")
    op.drop_index("ix_discovery_findings_case_id", table_name="discovery_findings")
    op.drop_table("discovery_findings")
    op.drop_index("ix_discovery_cases_patient_id", table_name="discovery_cases")
    op.drop_index("ix_discovery_cases_user_id", table_name="discovery_cases")
    op.drop_table("discovery_cases")
