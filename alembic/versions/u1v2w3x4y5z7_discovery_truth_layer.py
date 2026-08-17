"""Discovery truth-layer identities, branches, gaps, evidence, monitoring.

Revision ID: u1v2w3x4y5z7
Revises: t0u1v2w3x4y5
Create Date: 2026-08-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "u1v2w3x4y5z7"
down_revision = "t0u1v2w3x4y5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("discovery_findings", sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("discovery_findings", sa.Column("source_event_id", sa.String(length=200), nullable=True))
    op.add_column("discovery_findings", sa.Column("identity_key", sa.String(length=64), nullable=True))
    op.add_column("discovery_findings", sa.Column("supersedes_finding_id", sa.CHAR(length=36), nullable=True))
    op.create_index("uq_discovery_findings_identity", "discovery_findings", ["case_id", "identity_key"], unique=True)
    op.create_table(
        "discovery_investigation_branches",
        sa.Column("id", sa.CHAR(length=36), primary_key=True),
        sa.Column("case_id", sa.CHAR(length=36), sa.ForeignKey("discovery_cases.id"), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("resolved_at", sa.String(length=40), nullable=True),
        sa.Column("source_event_id", sa.String(length=200), nullable=True),
        sa.Column("close_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("uq_discovery_branches_case_code", "discovery_investigation_branches", ["case_id", "code"], unique=True)
    op.create_table(
        "discovery_evidence_gaps",
        sa.Column("id", sa.CHAR(length=36), primary_key=True),
        sa.Column("case_id", sa.CHAR(length=36), sa.ForeignKey("discovery_cases.id"), nullable=False),
        sa.Column("branch_code", sa.String(length=80), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("source_event_id", sa.String(length=200), nullable=False),
        sa.Column("identity_key", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("uq_discovery_gaps_identity", "discovery_evidence_gaps", ["case_id", "identity_key"], unique=True)
    op.create_table(
        "discovery_workup_items",
        sa.Column("id", sa.CHAR(length=36), primary_key=True),
        sa.Column("case_id", sa.CHAR(length=36), sa.ForeignKey("discovery_cases.id"), nullable=False),
        sa.Column("test_code", sa.String(length=80), nullable=False),
        sa.Column("raw_label", sa.String(length=200), nullable=False),
        sa.Column("normalized_result", sa.String(length=40), nullable=True),
        sa.Column("occurrence_date", sa.String(length=40), nullable=True),
        sa.Column("source_event_id", sa.String(length=200), nullable=False),
        sa.Column("identity_key", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("uq_discovery_workup_identity", "discovery_workup_items", ["case_id", "identity_key"], unique=True)
    op.create_table(
        "discovery_evidence_edges",
        sa.Column("id", sa.CHAR(length=36), primary_key=True),
        sa.Column("case_id", sa.CHAR(length=36), sa.ForeignKey("discovery_cases.id"), nullable=False),
        sa.Column("branch_code", sa.String(length=80), nullable=False),
        sa.Column("workup_id", sa.CHAR(length=36), sa.ForeignKey("discovery_workup_items.id"), nullable=True),
        sa.Column("relationship", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("identity_key", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("uq_discovery_evidence_identity", "discovery_evidence_edges", ["case_id", "identity_key"], unique=True)
    op.create_table(
        "discovery_monitoring_events",
        sa.Column("id", sa.CHAR(length=36), primary_key=True),
        sa.Column("case_id", sa.CHAR(length=36), sa.ForeignKey("discovery_cases.id"), nullable=False),
        sa.Column("target", sa.String(length=120), nullable=False),
        sa.Column("observation_time", sa.String(length=40), nullable=False),
        sa.Column("outcome_kind", sa.String(length=32), nullable=False),
        sa.Column("exposure", sa.String(length=80), nullable=True),
        sa.Column("adherence", sa.String(length=80), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("source_event_id", sa.String(length=200), nullable=False),
        sa.Column("identity_key", sa.String(length=64), nullable=False),
        sa.Column("causal_claim", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("uq_discovery_monitoring_identity", "discovery_monitoring_events", ["case_id", "identity_key"], unique=True)


def downgrade() -> None:
    op.drop_table("discovery_monitoring_events")
    op.drop_table("discovery_evidence_edges")
    op.drop_table("discovery_workup_items")
    op.drop_table("discovery_evidence_gaps")
    op.drop_table("discovery_investigation_branches")
    op.drop_index("uq_discovery_findings_identity", table_name="discovery_findings")
    op.drop_column("discovery_findings", "supersedes_finding_id")
    op.drop_column("discovery_findings", "identity_key")
    op.drop_column("discovery_findings", "source_event_id")
    op.drop_column("discovery_findings", "active")
