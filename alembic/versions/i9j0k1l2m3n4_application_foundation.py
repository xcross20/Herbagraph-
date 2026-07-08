"""Application foundation: organizations, patient profiles, patient context

Revision ID: i9j0k1l2m3n4
Revises: h8i9j0k1l2m3
Create Date: 2026-07-08
"""

from alembic import op
import sqlalchemy as sa
import app.models.mixins

revision = "i9j0k1l2m3n4"
down_revision = "h8i9j0k1l2m3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False, server_default="solo_practitioner"),
        sa.Column("id", app.models.mixins.GUID(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.add_column("users", sa.Column("full_name", sa.String(length=200), nullable=True))
    op.add_column(
        "users",
        sa.Column("organization_id", app.models.mixins.GUID(length=36), nullable=True),
    )
    op.create_foreign_key("fk_users_organization_id", "users", "organizations", ["organization_id"], ["id"])

    op.add_column("patients", sa.Column("display_name", sa.String(length=120), nullable=False, server_default="Patient"))
    op.add_column("patients", sa.Column("date_of_birth", sa.Date(), nullable=True))
    op.add_column("patients", sa.Column("notes", sa.Text(), nullable=True))
    op.add_column(
        "patients",
        sa.Column("organization_id", app.models.mixins.GUID(length=36), nullable=True),
    )
    op.create_foreign_key(
        "fk_patients_organization_id", "patients", "organizations", ["organization_id"], ["id"]
    )
    op.alter_column("patients", "display_name", server_default=None)

    op.create_table(
        "patient_context",
        sa.Column("patient_id", app.models.mixins.GUID(length=36), nullable=False),
        sa.Column("context_type", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("source", sa.String(length=50), nullable=False, server_default="user"),
        sa.Column("id", app.models.mixins.GUID(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_patient_context_patient_id", "patient_context", ["patient_id"])

    op.add_column(
        "analysis_sessions",
        sa.Column("analysis_type", sa.String(length=40), nullable=False, server_default="multi_report_snapshot"),
    )
    op.add_column("analysis_sessions", sa.Column("report_confidence", sa.Float(), nullable=True))
    op.alter_column("analysis_sessions", "analysis_type", server_default=None)


def downgrade() -> None:
    op.drop_column("analysis_sessions", "report_confidence")
    op.drop_column("analysis_sessions", "analysis_type")
    op.drop_index("ix_patient_context_patient_id", table_name="patient_context")
    op.drop_table("patient_context")
    op.drop_constraint("fk_patients_organization_id", "patients", type_="foreignkey")
    op.drop_column("patients", "organization_id")
    op.drop_column("patients", "notes")
    op.drop_column("patients", "date_of_birth")
    op.drop_column("patients", "display_name")
    op.drop_constraint("fk_users_organization_id", "users", type_="foreignkey")
    op.drop_column("users", "organization_id")
    op.drop_column("users", "full_name")
    op.drop_table("organizations")