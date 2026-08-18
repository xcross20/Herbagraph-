"""Safety Engine v1.0 graph tables

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-08
"""

from alembic import op
import sqlalchemy as sa

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "safety_graph_nodes",
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("node_type", sa.String(length=30), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("aliases", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "safety_graph_edges",
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("source_node_id", sa.CHAR(length=36), nullable=False),
        sa.Column("target_node_id", sa.CHAR(length=36), nullable=False),
        sa.Column("relationship_type", sa.String(length=30), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("mechanism", sa.Text(), nullable=False),
        sa.Column("evidence_level", sa.String(length=30), nullable=True),
        sa.Column("citations", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["source_node_id"], ["safety_graph_nodes.id"]),
        sa.ForeignKeyConstraint(["target_node_id"], ["safety_graph_nodes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("safety_graph_edges")
    op.drop_table("safety_graph_nodes")