"""Canonical intervention registry and enrichment pipeline tables

Revision ID: l2m3n4o5p6q7
Revises: k1l2m3n4o5p6
Create Date: 2026-07-14
"""

from alembic import op
import sqlalchemy as sa

revision = "l2m3n4o5p6q7"
down_revision = "k1l2m3n4o5p6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "canonical_entities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("entity_id", sa.String(length=24), nullable=False),
        sa.Column("canonical_name", sa.String(length=200), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("entity_type", sa.String(length=30), nullable=False),
        sa.Column("subtype", sa.String(length=40), nullable=True),
        sa.Column("species", sa.String(length=200), nullable=True),
        sa.Column("plant_part", sa.String(length=80), nullable=True),
        sa.Column("preparation", sa.String(length=120), nullable=True),
        sa.Column("coverage_tier", sa.String(length=10), nullable=False, server_default="tier_c"),
        sa.Column("review_status", sa.String(length=30), nullable=False, server_default="machine_generated"),
        sa.Column("intervention_id", sa.Uuid(), nullable=True),
        sa.Column("compound_id", sa.Uuid(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["compound_id"], ["compounds.id"]),
        sa.ForeignKeyConstraint(["intervention_id"], ["interventions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("entity_id"),
    )
    op.create_index("ix_canonical_entities_entity_type", "canonical_entities", ["entity_type"])

    op.create_table(
        "entity_synonyms",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("entity_id_fk", sa.Uuid(), nullable=False),
        sa.Column("synonym", sa.String(length=200), nullable=False),
        sa.Column("synonym_normalized", sa.String(length=200), nullable=False),
        sa.Column("locale", sa.String(length=10), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["entity_id_fk"], ["canonical_entities.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("entity_id_fk", "synonym_normalized"),
    )
    op.create_index("ix_entity_synonyms_synonym_normalized", "entity_synonyms", ["synonym_normalized"])

    op.create_table(
        "entity_external_ids",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("entity_id_fk", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("external_id", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["entity_id_fk"], ["canonical_entities.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source", "external_id"),
    )
    op.create_index("ix_entity_external_ids_entity_id_fk", "entity_external_ids", ["entity_id_fk"])

    op.create_table(
        "graph_edges",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_entity_id", sa.Uuid(), nullable=False),
        sa.Column("target_entity_id", sa.Uuid(), nullable=False),
        sa.Column("relationship_type", sa.String(length=30), nullable=False),
        sa.Column("direction", sa.String(length=40), nullable=True),
        sa.Column("evidence_type", sa.String(length=30), nullable=False, server_default="mechanistic"),
        sa.Column("study_design", sa.String(length=80), nullable=True),
        sa.Column("population", sa.String(length=200), nullable=True),
        sa.Column("citation", sa.String(length=80), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("review_status", sa.String(length=30), nullable=False, server_default="machine_generated"),
        sa.Column("source_provenance", sa.String(length=120), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["source_entity_id"], ["canonical_entities.id"]),
        sa.ForeignKeyConstraint(["target_entity_id"], ["canonical_entities.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_graph_edges_source_entity_id", "graph_edges", ["source_entity_id"])
    op.create_index("ix_graph_edges_target_entity_id", "graph_edges", ["target_entity_id"])

    op.create_table(
        "enrichment_queue",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("query_name", sa.String(length=200), nullable=False),
        sa.Column("query_normalized", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("entity_id_fk", sa.Uuid(), nullable=True),
        sa.Column("result_summary", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("requested_by", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["entity_id_fk"], ["canonical_entities.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_enrichment_queue_query_name", "enrichment_queue", ["query_name"])
    op.create_index("ix_enrichment_queue_query_normalized", "enrichment_queue", ["query_normalized"])


def downgrade() -> None:
    op.drop_table("enrichment_queue")
    op.drop_table("graph_edges")
    op.drop_table("entity_external_ids")
    op.drop_table("entity_synonyms")
    op.drop_table("canonical_entities")