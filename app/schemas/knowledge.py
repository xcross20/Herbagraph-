"""Pydantic schemas for canonical intervention registry APIs."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import (
    CanonicalEntitySubtype,
    CanonicalEntityType,
    CoverageTier,
    EnrichmentQueueStatus,
    EntityReviewStatus,
    GraphEvidenceType,
    GraphRelationshipType,
)


class EntitySynonymRead(BaseModel):
    synonym: str
    locale: str | None = None

    model_config = {"from_attributes": True}


class EntityExternalIdRead(BaseModel):
    source: str
    external_id: str

    model_config = {"from_attributes": True}


class CanonicalEntityRead(BaseModel):
    id: uuid.UUID
    entity_id: str
    canonical_name: str
    display_name: str
    entity_type: CanonicalEntityType
    subtype: CanonicalEntitySubtype | None = None
    species: str | None = None
    plant_part: str | None = None
    preparation: str | None = None
    coverage_tier: CoverageTier
    review_status: EntityReviewStatus
    synonyms: list[EntitySynonymRead] = Field(default_factory=list)
    external_ids: list[EntityExternalIdRead] = Field(default_factory=list)
    notes: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CanonicalEntityCreate(BaseModel):
    canonical_name: str
    display_name: str | None = None
    entity_type: CanonicalEntityType
    subtype: CanonicalEntitySubtype | None = None
    species: str | None = None
    plant_part: str | None = None
    preparation: str | None = None
    synonyms: list[str] = Field(default_factory=list)
    coverage_tier: CoverageTier = CoverageTier.TIER_C
    review_status: EntityReviewStatus = EntityReviewStatus.MACHINE_GENERATED


class GraphEdgeRead(BaseModel):
    id: uuid.UUID
    source_entity_id: uuid.UUID
    target_entity_id: uuid.UUID
    relationship_type: GraphRelationshipType
    direction: str | None = None
    evidence_type: GraphEvidenceType
    study_design: str | None = None
    population: str | None = None
    citation: str | None = None
    confidence: float | None = None
    review_status: EntityReviewStatus
    source_provenance: str | None = None
    notes: str | None = None

    model_config = {"from_attributes": True}


class EnrichmentQueueItemRead(BaseModel):
    id: uuid.UUID
    query_name: str
    status: EnrichmentQueueStatus
    priority: int
    entity_id_fk: uuid.UUID | None = None
    result_summary: str | None = None
    error_message: str | None = None
    requested_by: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EnrichmentEnqueueRequest(BaseModel):
    query_name: str
    priority: int = 100


class KnowledgeCoverageSummary(BaseModel):
    entity_count: int
    tier_a_count: int
    tier_b_count: int
    tier_c_count: int
    production_approved_count: int
    pending_enrichment_count: int
    evidence_coverage_label: str
    entity_coverage_label: str
    last_evidence_review: str


class KnowledgeIntegrationsStatus(BaseModel):
    """Operator-facing integration readiness for enrichment + bootstrap."""

    usda_configured: bool
    usda_key_present: bool
    usda_live_ok: bool | None = None
    usda_sample_count: int | None = None
    usda_error: str | None = None
    openai_configured: bool
    minimax_configured: bool
    ncbi_configured: bool
    knowledge_paths: list[str] = ["legacy", "canonical"]


class DeepEnrichmentSeedResponse(BaseModel):
    enqueued: int
    skipped_with_ids: int
    scanned: int