"""Add report_feedback and validation_events tables

Revision ID: g7h8i9j0k1l2
Revises: f6a7b8c9d0e1
Create Date: 2026-07-08
"""

from alembic import op
import sqlalchemy as sa
import app.models.mixins

revision = "g7h8i9j0k1l2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "report_feedback",
        sa.Column("report_id", app.models.mixins.GUID(length=36), nullable=False),
        sa.Column("user_id", app.models.mixins.GUID(length=36), nullable=False),
        sa.Column("clinical_usefulness_score", sa.Integer(), nullable=False),
        sa.Column("reasoning_agreement", sa.String(length=20), nullable=False),
        sa.Column("trust_score", sa.Integer(), nullable=True),
        sa.Column("estimated_time_saved_minutes", sa.Integer(), nullable=True),
        sa.Column("most_useful_section", sa.String(length=80), nullable=True),
        sa.Column("least_useful_section", sa.String(length=80), nullable=True),
        sa.Column("patient_encounter_comfort", sa.String(length=30), nullable=True),
        sa.Column("would_use_again", sa.String(length=20), nullable=True),
        sa.Column("safety_concerns", sa.Text(), nullable=True),
        sa.Column("free_text_feedback", sa.Text(), nullable=True),
        sa.Column("id", app.models.mixins.GUID(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "clinical_usefulness_score >= 1 AND clinical_usefulness_score <= 5",
            name="report_feedback_usefulness_range",
        ),
        sa.CheckConstraint(
            "trust_score IS NULL OR (trust_score >= 1 AND trust_score <= 5)",
            name="report_feedback_trust_range",
        ),
        sa.ForeignKeyConstraint(["report_id"], ["recommendation_reports.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_report_feedback_report_id", "report_feedback", ["report_id"])
    op.create_index("ix_report_feedback_user_id", "report_feedback", ["user_id"])

    op.create_table(
        "validation_events",
        sa.Column("report_id", app.models.mixins.GUID(length=36), nullable=True),
        sa.Column("user_id", app.models.mixins.GUID(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("section_name", sa.String(length=80), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("id", app.models.mixins.GUID(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["report_id"], ["recommendation_reports.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_validation_events_report_id", "validation_events", ["report_id"])
    op.create_index("ix_validation_events_user_id", "validation_events", ["user_id"])
    op.create_index("ix_validation_events_event_type", "validation_events", ["event_type"])


def downgrade() -> None:
    op.drop_index("ix_validation_events_event_type", table_name="validation_events")
    op.drop_index("ix_validation_events_user_id", table_name="validation_events")
    op.drop_index("ix_validation_events_report_id", table_name="validation_events")
    op.drop_table("validation_events")
    op.drop_index("ix_report_feedback_user_id", table_name="report_feedback")
    op.drop_index("ix_report_feedback_report_id", table_name="report_feedback")
    op.drop_table("report_feedback")