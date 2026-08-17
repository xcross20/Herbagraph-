"""Persistent Guided Discovery Case, Finding, and Hypothesis rows."""

from __future__ import annotations

import uuid

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import (
    DiscoveryBranchStatus,
    DiscoveryCaseStatus,
    DiscoveryClaimStatus,
    DiscoveryEvidenceRelationship,
    DiscoveryEvidenceType,
    DiscoveryFindingKind,
    DiscoveryGapResolutionType,
    DiscoveryGapStatus,
    DiscoveryHypothesisStatus,
    DiscoveryLaterality,
    DiscoveryOutcomeStatus,
    DiscoveryProvenance,
    DiscoveryTemporality,
    DiscoveryTestAccessClass,
    DiscoveryTurnRole,
    DiscoveryVerificationState,
    DiscoveryWorkupCompletion,
    DiscoveryWorkupResult,
)
from app.models.mixins import GUID, TimestampMixin, UUIDPrimaryKeyMixin


class DiscoveryCase(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """The Case is the source of truth. Chat is only an interface."""

    __tablename__ = "discovery_cases"

    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False, index=True)
    patient_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("patients.id"), nullable=True, index=True)
    presenting_concern: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[DiscoveryCaseStatus] = mapped_column(
        Enum(DiscoveryCaseStatus, native_enum=False, length=20),
        default=DiscoveryCaseStatus.OPEN,
        nullable=False,
    )
    lab_report_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("lab_reports.id"), nullable=True)
    investigation_coverage: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    stage: Mapped[str] = mapped_column(String(40), nullable=False, default="opening")
    problem_representation: Mapped[str | None] = mapped_column(Text, nullable=True)
    literature_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    safety_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    findings: Mapped[list["DiscoveryFinding"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )
    hypotheses: Mapped[list["DiscoveryHypothesis"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )
    outcomes: Mapped[list["DiscoveryOutcome"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )
    turns: Mapped[list["DiscoveryTurn"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )
    map_versions: Mapped[list["DiscoveryMapVersion"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )


class DiscoveryFinding(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "discovery_findings"

    case_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("discovery_cases.id"), nullable=False, index=True)
    kind: Mapped[DiscoveryFindingKind] = mapped_column(
        Enum(DiscoveryFindingKind, native_enum=False, length=20), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    branch: Mapped[str | None] = mapped_column(String(40), nullable=True)
    source: Mapped[str] = mapped_column(String(40), nullable=False, default="user")
    canonical_concept_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalized_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    provenance: Mapped[DiscoveryProvenance | None] = mapped_column(
        Enum(DiscoveryProvenance, native_enum=False, length=40), nullable=True
    )
    verification_state: Mapped[DiscoveryVerificationState | None] = mapped_column(
        Enum(DiscoveryVerificationState, native_enum=False, length=20), nullable=True
    )
    temporality: Mapped[DiscoveryTemporality | None] = mapped_column(
        Enum(DiscoveryTemporality, native_enum=False, length=20), nullable=True
    )
    onset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    laterality: Mapped[DiscoveryLaterality | None] = mapped_column(
        Enum(DiscoveryLaterality, native_enum=False, length=20), nullable=True
    )
    body_region: Mapped[str | None] = mapped_column(String(80), nullable=True)
    source_turn_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("discovery_turns.id"), nullable=True)
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    supersedes_finding_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("discovery_findings.id"), nullable=True
    )
    retracted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retraction_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    case: Mapped[DiscoveryCase] = relationship(back_populates="findings")


class DiscoveryHypothesis(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "discovery_hypotheses"

    case_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("discovery_cases.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    branch: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[DiscoveryHypothesisStatus] = mapped_column(
        Enum(DiscoveryHypothesisStatus, native_enum=False, length=20),
        default=DiscoveryHypothesisStatus.OPEN,
        nullable=False,
    )
    investigation_relevance: Mapped[float] = mapped_column(Float, nullable=False)
    diagnostic_certainty: Mapped[float] = mapped_column(Float, nullable=False)
    investigation_coverage: Mapped[float] = mapped_column(Float, nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    missing_markers: Mapped[str | None] = mapped_column(Text, nullable=True)
    investigations: Mapped[str | None] = mapped_column(Text, nullable=True)

    case: Mapped[DiscoveryCase] = relationship(back_populates="hypotheses")


class DiscoveryOutcome(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A recorded check — done, not done, or still pending. Not a diagnosis."""

    __tablename__ = "discovery_outcomes"

    case_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("discovery_cases.id"), nullable=False, index=True)
    hypothesis_code: Mapped[str] = mapped_column(String(80), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[DiscoveryOutcomeStatus] = mapped_column(
        Enum(DiscoveryOutcomeStatus, native_enum=False, length=20),
        default=DiscoveryOutcomeStatus.PENDING,
        nullable=False,
    )
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    question_code: Mapped[str | None] = mapped_column(String(120), nullable=True)

    case: Mapped[DiscoveryCase] = relationship(back_populates="outcomes")


class DiscoveryTurn(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Chat is only an interface. The Case remains the source of truth."""

    __tablename__ = "discovery_turns"

    case_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("discovery_cases.id"), nullable=False, index=True)
    role: Mapped[DiscoveryTurnRole] = mapped_column(
        Enum(DiscoveryTurnRole, native_enum=False, length=12), nullable=False
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="note")
    question_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    intent: Mapped[str | None] = mapped_column(String(80), nullable=True)
    action_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    stage: Mapped[str | None] = mapped_column(String(40), nullable=True)
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)

    case: Mapped[DiscoveryCase] = relationship(back_populates="turns")


class DiscoveryMapVersion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Append-only Investigation Map. Never overwrite history."""

    __tablename__ = "discovery_map_versions"

    case_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("discovery_cases.id"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)

    case: Mapped[DiscoveryCase] = relationship(back_populates="map_versions")


class DiscoveryTestPlanItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Labs recommended by Discovery, fulfilled in the existing workspace."""

    __tablename__ = "discovery_test_plan_items"

    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False, index=True)
    case_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("discovery_cases.id"), nullable=False, index=True)
    patient_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("patients.id"), nullable=True, index=True)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="added")
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="discovery")
    canonical_test_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("discovery_investigation_branches.id"), nullable=True
    )
    evidence_gap_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("discovery_evidence_gaps.id"), nullable=True
    )
    information_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    priority: Mapped[int | None] = mapped_column(Integer, nullable=True)
    access_class: Mapped[DiscoveryTestAccessClass | None] = mapped_column(
        Enum(DiscoveryTestAccessClass, native_enum=False, length=40), nullable=True
    )
    clinical_review_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    provider: Mapped[str | None] = mapped_column(String(80), nullable=True)
    provider_test_code: Mapped[str | None] = mapped_column(String(80), nullable=True)


class DiscoveryLongitudinalSnapshot(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Patient-level memory generated from existing labs and cases."""

    __tablename__ = "discovery_longitudinal_snapshots"

    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False, index=True)
    patient_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("patients.id"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)


class DiscoveryTimelineEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "discovery_timeline_events"

    case_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("discovery_cases.id"), nullable=False, index=True)
    patient_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("patients.id"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False, default="symptom")
    label: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    occurred_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    occurred_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    date_precision: Mapped[str | None] = mapped_column(String(20), nullable=True)
    provenance: Mapped[DiscoveryProvenance] = mapped_column(
        Enum(DiscoveryProvenance, native_enum=False, length=40),
        default=DiscoveryProvenance.PATIENT_REPORTED,
        nullable=False,
    )
    verification_state: Mapped[DiscoveryVerificationState] = mapped_column(
        Enum(DiscoveryVerificationState, native_enum=False, length=20),
        default=DiscoveryVerificationState.REPORTED,
        nullable=False,
    )
    source_turn_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    supersedes_event_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("discovery_timeline_events.id"), nullable=True
    )


class DiscoveryPatientInterpretation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "discovery_patient_interpretations"

    case_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("discovery_cases.id"), nullable=False, index=True)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_concept: Mapped[str | None] = mapped_column(String(160), nullable=True)
    source_turn_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class DiscoveryInvestigationBranch(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "discovery_investigation_branches"
    __table_args__ = (UniqueConstraint("case_id", "code", name="uq_discovery_branch_case_code"),)

    case_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("discovery_cases.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False, default="general")
    status: Mapped[DiscoveryBranchStatus] = mapped_column(
        Enum(DiscoveryBranchStatus, native_enum=False, length=50),
        default=DiscoveryBranchStatus.NOT_EVALUATED,
        nullable=False,
    )
    investigation_relevance: Mapped[float] = mapped_column(Float, nullable=False, default=0.4)
    coverage: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    coverage_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.4)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    opened_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reopened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str] = mapped_column(String(40), nullable=False, default="guide")


class DiscoveryPriorWorkupItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "discovery_prior_workup_items"

    case_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("discovery_cases.id"), nullable=False, index=True)
    patient_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("patients.id"), nullable=True, index=True)
    canonical_test_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    raw_test_name: Mapped[str] = mapped_column(String(200), nullable=False)
    performed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completion_state: Mapped[DiscoveryWorkupCompletion] = mapped_column(
        Enum(DiscoveryWorkupCompletion, native_enum=False, length=40),
        default=DiscoveryWorkupCompletion.PATIENT_REPORTED_COMPLETED,
        nullable=False,
    )
    result_state: Mapped[DiscoveryWorkupResult] = mapped_column(
        Enum(DiscoveryWorkupResult, native_enum=False, length=40),
        default=DiscoveryWorkupResult.UNKNOWN_RESULT,
        nullable=False,
    )
    verification_state: Mapped[DiscoveryVerificationState] = mapped_column(
        Enum(DiscoveryVerificationState, native_enum=False, length=20),
        default=DiscoveryVerificationState.REPORTED,
        nullable=False,
    )
    raw_result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_turn_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    protocol_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    coverage_assessment_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class DiscoveryEvidenceEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "discovery_evidence_events"

    case_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("discovery_cases.id"), nullable=False, index=True)
    patient_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("patients.id"), nullable=True, index=True)
    evidence_type: Mapped[DiscoveryEvidenceType] = mapped_column(
        Enum(DiscoveryEvidenceType, native_enum=False, length=40), nullable=False
    )
    source_system: Mapped[str] = mapped_column(String(40), nullable=False, default="discovery")
    source_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    canonical_concept: Mapped[str | None] = mapped_column(String(160), nullable=True)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    structured_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    provenance: Mapped[DiscoveryProvenance] = mapped_column(
        Enum(DiscoveryProvenance, native_enum=False, length=40),
        default=DiscoveryProvenance.SYSTEM_INFERRED,
        nullable=False,
    )
    verification_state: Mapped[DiscoveryVerificationState] = mapped_column(
        Enum(DiscoveryVerificationState, native_enum=False, length=20),
        default=DiscoveryVerificationState.UNVERIFIED,
        nullable=False,
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DiscoveryEvidenceGap(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "discovery_evidence_gaps"
    __table_args__ = (UniqueConstraint("case_id", "code", name="uq_discovery_gap_case_code"),)

    case_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("discovery_cases.id"), nullable=False, index=True)
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("discovery_investigation_branches.id"), nullable=True, index=True
    )
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    information_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    actionability: Mapped[str] = mapped_column(String(40), nullable=False, default="question")
    resolution_type: Mapped[DiscoveryGapResolutionType] = mapped_column(
        Enum(DiscoveryGapResolutionType, native_enum=False, length=40),
        default=DiscoveryGapResolutionType.QUESTION,
        nullable=False,
    )
    canonical_test_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    requested_document_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[DiscoveryGapStatus] = mapped_column(
        Enum(DiscoveryGapStatus, native_enum=False, length=30),
        default=DiscoveryGapStatus.OPEN,
        nullable=False,
    )
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_evidence_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)


class DiscoveryBranchEvidence(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "discovery_branch_evidence"

    branch_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("discovery_investigation_branches.id"), nullable=False, index=True
    )
    finding_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("discovery_findings.id"), nullable=True)
    evidence_event_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("discovery_evidence_events.id"), nullable=True
    )
    prior_workup_item_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("discovery_prior_workup_items.id"), nullable=True
    )
    relationship: Mapped[DiscoveryEvidenceRelationship] = mapped_column(
        Enum(DiscoveryEvidenceRelationship, native_enum=False, length=30),
        nullable=False,
    )
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    provenance: Mapped[DiscoveryProvenance] = mapped_column(
        Enum(DiscoveryProvenance, native_enum=False, length=40),
        default=DiscoveryProvenance.SYSTEM_INFERRED,
        nullable=False,
    )
    created_by: Mapped[str] = mapped_column(String(40), nullable=False, default="guide")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class DiscoveryReasoningClaim(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "discovery_reasoning_claims"

    case_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("discovery_cases.id"), nullable=False, index=True)
    turn_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    claim_type: Mapped[str] = mapped_column(String(40), nullable=False, default="investigation")
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    structured_claim: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    evidence_ids: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[DiscoveryClaimStatus] = mapped_column(
        Enum(DiscoveryClaimStatus, native_enum=False, length=20),
        default=DiscoveryClaimStatus.ACTIVE,
        nullable=False,
    )


class DiscoveryReasoningCorrection(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "discovery_reasoning_corrections"

    case_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("discovery_cases.id"), nullable=False, index=True)
    original_claim_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("discovery_reasoning_claims.id"), nullable=True
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    triggering_evidence_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    replacement_claim_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
