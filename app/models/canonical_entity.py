"""Canonical intervention universe — Level 1–4 ontology tables."""

from __future__ import annotations

import uuid

from sqlalchemy import Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import (
    CanonicalEntitySubtype,
    CanonicalEntityType,
    CoverageTier,
    EnrichmentQueueStatus,
    EntityReviewStatus,
    ExternalIdSource,
    GraphEvidenceType,
    GraphRelationshipType,
)
from app.models.mixins import GUID, TimestampMixin, UUIDPrimaryKeyMixin

ENTITY_ID_PREFIX: dict[CanonicalEntityType, str] = {
    CanonicalEntityType.FOOD: "HG-FOOD",
    CanonicalEntityType.BOTANICAL: "HG-BOT",
    CanonicalEntityType.NUTRIENT: "HG-NUT",
    CanonicalEntityType.SUPPLEMENT: "HG-SUP",
    CanonicalEntityType.COMPOUND: "HG-CMP",
    CanonicalEntityType.LIFESTYLE: "HG-LIF",
    CanonicalEntityType.MEDICATION: "HG-MED",
    CanonicalEntityType.PEPTIDE: "HG-PEP",
    CanonicalEntityType.PROCEDURE: "HG-PRO",
    CanonicalEntityType.DEVICE: "HG-DEV",
    CanonicalEntityType.PATHWAY: "HG-PATH",
    CanonicalEntityType.BIOMARKER: "HG-BMK",
}


class CanonicalEntity(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Master registry for foods, botanicals, nutrients, supplements, and compounds."""

    __tablename__ = "canonical_entities"

    entity_id: Mapped[str] = mapped_column(String(24), unique=True, nullable=False)
    canonical_name: Mapped[str] = mapped_column(String(200), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    entity_type: Mapped[CanonicalEntityType] = mapped_column(
        String(30), nullable=False, index=True
    )
    subtype: Mapped[CanonicalEntitySubtype | None] = mapped_column(String(40), nullable=True)
    species: Mapped[str | None] = mapped_column(String(200), nullable=True)
    plant_part: Mapped[str | None] = mapped_column(String(80), nullable=True)
    preparation: Mapped[str | None] = mapped_column(String(120), nullable=True)
    coverage_tier: Mapped[CoverageTier] = mapped_column(
        String(10), nullable=False, default=CoverageTier.TIER_C.value
    )
    review_status: Mapped[EntityReviewStatus] = mapped_column(
        String(30), nullable=False, default=EntityReviewStatus.MACHINE_GENERATED.value
    )
    intervention_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("interventions.id"), nullable=True
    )
    compound_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("compounds.id"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    synonyms: Mapped[list["EntitySynonym"]] = relationship(
        back_populates="entity", cascade="all, delete-orphan"
    )
    external_ids: Mapped[list["EntityExternalId"]] = relationship(
        back_populates="entity", cascade="all, delete-orphan"
    )
    outgoing_edges: Mapped[list["GraphEdge"]] = relationship(
        back_populates="source_entity",
        foreign_keys="GraphEdge.source_entity_id",
        cascade="all, delete-orphan",
    )
    incoming_edges: Mapped[list["GraphEdge"]] = relationship(
        back_populates="target_entity",
        foreign_keys="GraphEdge.target_entity_id",
        cascade="all, delete-orphan",
    )


class EntitySynonym(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Level 2 — alias resolution to prevent duplicate nodes."""

    __tablename__ = "entity_synonyms"
    __table_args__ = (UniqueConstraint("entity_id_fk", "synonym_normalized"),)

    entity_id_fk: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("canonical_entities.id"), nullable=False, index=True
    )
    synonym: Mapped[str] = mapped_column(String(200), nullable=False)
    synonym_normalized: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    locale: Mapped[str | None] = mapped_column(String(10), nullable=True)

    entity: Mapped["CanonicalEntity"] = relationship(back_populates="synonyms")


class EntityExternalId(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """External normalization identifiers (PubChem, ChEBI, USDA FDC, etc.)."""

    __tablename__ = "entity_external_ids"
    __table_args__ = (UniqueConstraint("source", "external_id"),)

    entity_id_fk: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("canonical_entities.id"), nullable=False, index=True
    )
    source: Mapped[ExternalIdSource] = mapped_column(String(20), nullable=False)
    external_id: Mapped[str] = mapped_column(String(80), nullable=False)

    entity: Mapped["CanonicalEntity"] = relationship(back_populates="external_ids")


class GraphEdge(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Level 3–4 — composition and evidence relationships with provenance."""

    __tablename__ = "graph_edges"

    source_entity_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("canonical_entities.id"), nullable=False, index=True
    )
    target_entity_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("canonical_entities.id"), nullable=False, index=True
    )
    relationship_type: Mapped[GraphRelationshipType] = mapped_column(String(30), nullable=False)
    direction: Mapped[str | None] = mapped_column(String(40), nullable=True)
    evidence_type: Mapped[GraphEvidenceType] = mapped_column(
        String(30), nullable=False, default=GraphEvidenceType.MECHANISTIC.value
    )
    study_design: Mapped[str | None] = mapped_column(String(80), nullable=True)
    population: Mapped[str | None] = mapped_column(String(200), nullable=True)
    citation: Mapped[str | None] = mapped_column(String(80), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    review_status: Mapped[EntityReviewStatus] = mapped_column(
        String(30), nullable=False, default=EntityReviewStatus.MACHINE_GENERATED.value
    )
    source_provenance: Mapped[str | None] = mapped_column(String(120), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    source_entity: Mapped["CanonicalEntity"] = relationship(
        back_populates="outgoing_edges", foreign_keys=[source_entity_id]
    )
    target_entity: Mapped["CanonicalEntity"] = relationship(
        back_populates="incoming_edges", foreign_keys=[target_entity_id]
    )


class EnrichmentQueueItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Automated expansion worker queue — candidate graph curation."""

    __tablename__ = "enrichment_queue"

    query_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    query_normalized: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    status: Mapped[EnrichmentQueueStatus] = mapped_column(
        String(20), nullable=False, default=EnrichmentQueueStatus.PENDING.value
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    entity_id_fk: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("canonical_entities.id"), nullable=True
    )
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_by: Mapped[str | None] = mapped_column(String(120), nullable=True)