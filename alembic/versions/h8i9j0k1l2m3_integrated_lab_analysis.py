"""Add analysis sessions and integrated biomarker merge tables

Revision ID: h8i9j0k1l2m3
Revises: g7h8i9j0k1l2
Create Date: 2026-07-08
"""

from alembic import op
import sqlalchemy as sa
import app.models.mixins

revision = "h8i9j0k1l2m3"
down_revision = "g7h8i9j0k1l2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analysis_sessions",
        sa.Column("user_id", app.models.mixins.GUID(length=36), nullable=False),
        sa.Column("patient_id", app.models.mixins.GUID(length=36), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("analysis_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("latest_report_id", app.models.mixins.GUID(length=36), nullable=True),
        sa.Column("id", app.models.mixins.GUID(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_analysis_sessions_user_id", "analysis_sessions", ["user_id"])

    op.create_table(
        "analysis_session_lab_reports",
        sa.Column("analysis_session_id", app.models.mixins.GUID(length=36), nullable=False),
        sa.Column("lab_report_id", app.models.mixins.GUID(length=36), nullable=False),
        sa.Column("panel_label", sa.String(length=120), nullable=True),
        sa.Column("id", app.models.mixins.GUID(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["analysis_session_id"], ["analysis_sessions.id"]),
        sa.ForeignKeyConstraint(["lab_report_id"], ["lab_reports.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_analysis_session_lab_reports_analysis_session_id",
        "analysis_session_lab_reports",
        ["analysis_session_id"],
    )
    op.create_index(
        "ix_analysis_session_lab_reports_lab_report_id",
        "analysis_session_lab_reports",
        ["lab_report_id"],
    )

    op.create_table(
        "integrated_biomarker_results",
        sa.Column("analysis_session_id", app.models.mixins.GUID(length=36), nullable=False),
        sa.Column("biomarker_name", sa.String(length=100), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(length=30), nullable=True),
        sa.Column("source_lab_report_id", app.models.mixins.GUID(length=36), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("merge_note", sa.Text(), nullable=True),
        sa.Column("is_snapshot", sa.Boolean(), nullable=False),
        sa.Column("id", app.models.mixins.GUID(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["analysis_session_id"], ["analysis_sessions.id"]),
        sa.ForeignKeyConstraint(["source_lab_report_id"], ["lab_reports.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_integrated_biomarker_results_analysis_session_id",
        "integrated_biomarker_results",
        ["analysis_session_id"],
    )

    op.add_column(
        "recommendation_reports",
        sa.Column("analysis_session_id", app.models.mixins.GUID(length=36), nullable=True),
    )
    op.create_foreign_key(
        "fk_recommendation_reports_analysis_session_id",
        "recommendation_reports",
        "analysis_sessions",
        ["analysis_session_id"],
        ["id"],
    )
    op.create_index(
        "ix_recommendation_reports_analysis_session_id",
        "recommendation_reports",
        ["analysis_session_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_recommendation_reports_analysis_session_id", table_name="recommendation_reports")
    op.drop_constraint(
        "fk_recommendation_reports_analysis_session_id",
        "recommendation_reports",
        type_="foreignkey",
    )
    op.drop_column("recommendation_reports", "analysis_session_id")

    op.drop_index("ix_integrated_biomarker_results_analysis_session_id", table_name="integrated_biomarker_results")
    op.drop_table("integrated_biomarker_results")

    op.drop_index("ix_analysis_session_lab_reports_lab_report_id", table_name="analysis_session_lab_reports")
    op.drop_index(
        "ix_analysis_session_lab_reports_analysis_session_id",
        table_name="analysis_session_lab_reports",
    )
    op.drop_table("analysis_session_lab_reports")

    op.drop_index("ix_analysis_sessions_user_id", table_name="analysis_sessions")
    op.drop_table("analysis_sessions")