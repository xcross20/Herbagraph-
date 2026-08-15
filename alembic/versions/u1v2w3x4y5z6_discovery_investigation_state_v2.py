"""Additive Discovery investigation graph and coverage ontology.

Revision ID: u1v2w3x4y5z6
Revises: t0u1v2w3x4y5
Create Date: 2026-08-15

No column rewrites. New tables plus nullable finding/test-plan columns only.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "u1v2w3x4y5z6"
down_revision = "t0u1v2w3x4y5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "discovery_timeline_events",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("case_id", sa.CHAR(36), sa.ForeignKey("discovery_cases.id"), nullable=False, index=True),
        sa.Column("patient_id", sa.CHAR(36), sa.ForeignKey("patients.id"), nullable=True, index=True),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("label", sa.String(240), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("occurred_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("occurred_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("date_precision", sa.String(20), nullable=True),
        sa.Column("provenance", sa.String(40), nullable=False),
        sa.Column("verification_state", sa.String(20), nullable=False),
        sa.Column("source_turn_id", sa.CHAR(36), nullable=True),
        sa.Column("source_document_id", sa.CHAR(36), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("supersedes_event_id", sa.CHAR(36), sa.ForeignKey("discovery_timeline_events.id"), nullable=True),
    )
    op.create_table(
        "discovery_patient_interpretations",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("case_id", sa.CHAR(36), sa.ForeignKey("discovery_cases.id"), nullable=False, index=True),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("normalized_concept", sa.String(160), nullable=True),
        sa.Column("source_turn_id", sa.CHAR(36), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_table(
        "discovery_investigation_branches",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("case_id", sa.CHAR(36), sa.ForeignKey("discovery_cases.id"), nullable=False, index=True),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("investigation_relevance", sa.Float(), nullable=False),
        sa.Column("coverage", sa.Float(), nullable=False),
        sa.Column("coverage_confidence", sa.Float(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("opened_reason", sa.Text(), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reopened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(40), nullable=False),
    )
    op.create_table(
        "discovery_prior_workup_items",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("case_id", sa.CHAR(36), sa.ForeignKey("discovery_cases.id"), nullable=False, index=True),
        sa.Column("patient_id", sa.CHAR(36), sa.ForeignKey("patients.id"), nullable=True, index=True),
        sa.Column("canonical_test_id", sa.CHAR(36), nullable=True),
        sa.Column("raw_test_name", sa.String(200), nullable=False),
        sa.Column("performed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completion_state", sa.String(40), nullable=False),
        sa.Column("result_state", sa.String(40), nullable=False),
        sa.Column("verification_state", sa.String(20), nullable=False),
        sa.Column("raw_result_summary", sa.Text(), nullable=True),
        sa.Column("source_turn_id", sa.CHAR(36), nullable=True),
        sa.Column("source_document_id", sa.CHAR(36), nullable=True),
        sa.Column("protocol_id", sa.String(80), nullable=True),
        sa.Column("coverage_assessment_json", sa.Text(), nullable=True),
    )
    op.create_table(
        "discovery_evidence_events",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("case_id", sa.CHAR(36), sa.ForeignKey("discovery_cases.id"), nullable=False, index=True),
        sa.Column("patient_id", sa.CHAR(36), sa.ForeignKey("patients.id"), nullable=True, index=True),
        sa.Column("evidence_type", sa.String(40), nullable=False),
        sa.Column("source_system", sa.String(40), nullable=False),
        sa.Column("source_id", sa.String(80), nullable=True),
        sa.Column("canonical_concept", sa.String(160), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("structured_payload", sa.Text(), nullable=True),
        sa.Column("provenance", sa.String(40), nullable=False),
        sa.Column("verification_state", sa.String(20), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "discovery_evidence_gaps",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("case_id", sa.CHAR(36), sa.ForeignKey("discovery_cases.id"), nullable=False, index=True),
        sa.Column("branch_id", sa.CHAR(36), sa.ForeignKey("discovery_investigation_branches.id"), nullable=True, index=True),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("information_value", sa.Float(), nullable=False),
        sa.Column("actionability", sa.String(40), nullable=False),
        sa.Column("resolution_type", sa.String(40), nullable=False),
        sa.Column("canonical_test_id", sa.CHAR(36), nullable=True),
        sa.Column("requested_document_type", sa.String(80), nullable=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_evidence_id", sa.CHAR(36), nullable=True),
    )
    op.create_table(
        "discovery_branch_evidence",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("branch_id", sa.CHAR(36), sa.ForeignKey("discovery_investigation_branches.id"), nullable=False, index=True),
        sa.Column("finding_id", sa.CHAR(36), sa.ForeignKey("discovery_findings.id"), nullable=True),
        sa.Column("evidence_event_id", sa.CHAR(36), sa.ForeignKey("discovery_evidence_events.id"), nullable=True),
        sa.Column("prior_workup_item_id", sa.CHAR(36), sa.ForeignKey("discovery_prior_workup_items.id"), nullable=True),
        sa.Column("relationship", sa.String(30), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("provenance", sa.String(40), nullable=False),
        sa.Column("created_by", sa.String(40), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_table(
        "discovery_reasoning_claims",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("case_id", sa.CHAR(36), sa.ForeignKey("discovery_cases.id"), nullable=False, index=True),
        sa.Column("turn_id", sa.CHAR(36), nullable=True),
        sa.Column("claim_type", sa.String(40), nullable=False),
        sa.Column("claim_text", sa.Text(), nullable=False),
        sa.Column("structured_claim", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("evidence_ids", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
    )
    op.create_table(
        "discovery_reasoning_corrections",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("case_id", sa.CHAR(36), sa.ForeignKey("discovery_cases.id"), nullable=False, index=True),
        sa.Column("original_claim_id", sa.CHAR(36), sa.ForeignKey("discovery_reasoning_claims.id"), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("triggering_evidence_id", sa.CHAR(36), nullable=True),
        sa.Column("replacement_claim_id", sa.CHAR(36), nullable=True),
    )
    for table in (
        "coverage_diagnostic_tests",
        "coverage_investigation_concepts",
    ):
        if table == "coverage_diagnostic_tests":
            op.create_table(
                table,
                sa.Column("id", sa.CHAR(36), primary_key=True),
                sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
                sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
                sa.Column("code", sa.String(80), nullable=False, unique=True),
                sa.Column("canonical_name", sa.String(200), nullable=False),
                sa.Column("modality", sa.String(40), nullable=False),
                sa.Column("specialty", sa.String(40), nullable=False),
                sa.Column("loinc_code", sa.String(40), nullable=True),
                sa.Column("description", sa.Text(), nullable=True),
            )
        else:
            op.create_table(
                table,
                sa.Column("id", sa.CHAR(36), primary_key=True),
                sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
                sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
                sa.Column("code", sa.String(80), nullable=False, unique=True),
                sa.Column("label", sa.String(200), nullable=False),
                sa.Column("description", sa.Text(), nullable=True),
            )
    op.create_table(
        "coverage_test_aliases",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("test_id", sa.CHAR(36), sa.ForeignKey("coverage_diagnostic_tests.id"), nullable=False, index=True),
        sa.Column("alias", sa.String(200), nullable=False),
        sa.Column("vendor", sa.String(80), nullable=True),
    )
    op.create_table(
        "coverage_test_protocols",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("test_id", sa.CHAR(36), sa.ForeignKey("coverage_diagnostic_tests.id"), nullable=False, index=True),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
    )
    op.create_table(
        "coverage_test_relations",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("test_id", sa.CHAR(36), sa.ForeignKey("coverage_diagnostic_tests.id"), nullable=False, index=True),
        sa.Column("protocol_id", sa.CHAR(36), sa.ForeignKey("coverage_test_protocols.id"), nullable=True),
        sa.Column("investigation_concept_id", sa.CHAR(36), sa.ForeignKey("coverage_investigation_concepts.id"), nullable=False, index=True),
        sa.Column("relation", sa.String(40), nullable=False),
        sa.Column("coverage_strength", sa.Float(), nullable=False),
        sa.Column("sensitivity_notes", sa.Text(), nullable=True),
        sa.Column("limitations", sa.Text(), nullable=True),
        sa.Column("evidence_source", sa.String(160), nullable=True),
    )
    op.create_table(
        "coverage_test_followups",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("from_test_id", sa.CHAR(36), sa.ForeignKey("coverage_diagnostic_tests.id"), nullable=False),
        sa.Column("to_test_id", sa.CHAR(36), sa.ForeignKey("coverage_diagnostic_tests.id"), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("condition", sa.String(160), nullable=True),
    )
    for name, col in (
        ("canonical_concept_id", sa.Column("canonical_concept_id", sa.CHAR(36), nullable=True)),
        ("raw_text", sa.Column("raw_text", sa.Text(), nullable=True)),
        ("normalized_value", sa.Column("normalized_value", sa.Text(), nullable=True)),
        ("provenance", sa.Column("provenance", sa.String(40), nullable=True)),
        ("verification_state", sa.Column("verification_state", sa.String(20), nullable=True)),
        ("temporality", sa.Column("temporality", sa.String(20), nullable=True)),
        ("onset_at", sa.Column("onset_at", sa.DateTime(timezone=True), nullable=True)),
        ("resolved_at", sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True)),
        ("laterality", sa.Column("laterality", sa.String(20), nullable=True)),
        ("body_region", sa.Column("body_region", sa.String(80), nullable=True)),
        ("source_turn_id", sa.Column("source_turn_id", sa.CHAR(36), sa.ForeignKey("discovery_turns.id"), nullable=True)),
        ("source_document_id", sa.Column("source_document_id", sa.CHAR(36), nullable=True)),
        ("source_page", sa.Column("source_page", sa.Integer(), nullable=True)),
        ("confidence", sa.Column("confidence", sa.Float(), nullable=True)),
        ("is_active", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true())),
        ("supersedes_finding_id", sa.Column("supersedes_finding_id", sa.CHAR(36), sa.ForeignKey("discovery_findings.id"), nullable=True)),
        ("retracted_at", sa.Column("retracted_at", sa.DateTime(timezone=True), nullable=True)),
        ("retraction_reason", sa.Column("retraction_reason", sa.Text(), nullable=True)),
    ):
        op.add_column("discovery_findings", col)
    for col in (
        sa.Column("canonical_test_id", sa.CHAR(36), nullable=True),
        sa.Column("branch_id", sa.CHAR(36), sa.ForeignKey("discovery_investigation_branches.id"), nullable=True),
        sa.Column("evidence_gap_id", sa.CHAR(36), sa.ForeignKey("discovery_evidence_gaps.id"), nullable=True),
        sa.Column("information_value", sa.Float(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=True),
        sa.Column("access_class", sa.String(40), nullable=True),
        sa.Column("clinical_review_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("provider", sa.String(80), nullable=True),
        sa.Column("provider_test_code", sa.String(80), nullable=True),
    ):
        op.add_column("discovery_test_plan_items", col)


def downgrade() -> None:
    for name in (
        "canonical_test_id",
        "branch_id",
        "evidence_gap_id",
        "information_value",
        "priority",
        "access_class",
        "clinical_review_required",
        "provider",
        "provider_test_code",
    ):
        op.drop_column("discovery_test_plan_items", name)
    for name in (
        "canonical_concept_id",
        "raw_text",
        "normalized_value",
        "provenance",
        "verification_state",
        "temporality",
        "onset_at",
        "resolved_at",
        "laterality",
        "body_region",
        "source_turn_id",
        "source_document_id",
        "source_page",
        "confidence",
        "is_active",
        "supersedes_finding_id",
        "retracted_at",
        "retraction_reason",
    ):
        op.drop_column("discovery_findings", name)
    for table in (
        "coverage_test_followups",
        "coverage_test_relations",
        "coverage_test_protocols",
        "coverage_test_aliases",
        "coverage_investigation_concepts",
        "coverage_diagnostic_tests",
        "discovery_reasoning_corrections",
        "discovery_reasoning_claims",
        "discovery_branch_evidence",
        "discovery_evidence_gaps",
        "discovery_evidence_events",
        "discovery_prior_workup_items",
        "discovery_investigation_branches",
        "discovery_patient_interpretations",
        "discovery_timeline_events",
    ):
        op.drop_table(table)
