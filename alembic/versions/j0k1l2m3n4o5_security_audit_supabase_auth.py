"""Security: Supabase auth fields and audit trail

Revision ID: j0k1l2m3n4o5
Revises: i9j0k1l2m3n4
Create Date: 2026-07-08
"""

from alembic import op
import sqlalchemy as sa
import app.models.mixins

revision = "j0k1l2m3n4o5"
down_revision = "i9j0k1l2m3n4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("auth_provider", sa.String(length=30), nullable=False, server_default="local"))
    op.add_column("users", sa.Column("external_auth_id", sa.String(length=64), nullable=True))
    op.create_index("ix_users_external_auth_id", "users", ["external_auth_id"], unique=True)
    op.alter_column("users", "auth_provider", server_default=None)

    op.create_table(
        "audit_events",
        sa.Column("user_id", app.models.mixins.GUID(length=36), nullable=True),
        sa.Column("patient_id", app.models.mixins.GUID(length=36), nullable=True),
        sa.Column("action", sa.String(length=60), nullable=False),
        sa.Column("resource_type", sa.String(length=40), nullable=True),
        sa.Column("resource_id", sa.String(length=64), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=300), nullable=True),
        sa.Column("id", app.models.mixins.GUID(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_events_user_id", "audit_events", ["user_id"])
    op.create_index("ix_audit_events_action", "audit_events", ["action"])
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_audit_events_created_at", table_name="audit_events")
    op.drop_index("ix_audit_events_action", table_name="audit_events")
    op.drop_index("ix_audit_events_user_id", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("ix_users_external_auth_id", table_name="users")
    op.drop_column("users", "external_auth_id")
    op.drop_column("users", "auth_provider")