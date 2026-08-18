"""Persistent Guided Discovery Case, Finding, and Hypothesis rows."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Enum, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import (
    BranchLifecycleStatus,
    DiscoveryCaseStatus,
    DiscoveryFindingKind,
    DiscoveryHypothesisStatus,
    DiscoveryOutcomeStatus,
    DiscoveryTurnRole,
    EvidenceRelationship,
    MonitoringOutcomeKind,
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
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    source_event_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    identity_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    supersedes_finding_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("discovery_findings.id"), nullable=True
    )

    case: Mapped[DiscoveryCase] = relationship(back_populates="findings")

    __table_args__ = (
        Index("uq_discovery_findings_identity", "case_id", "identity_key", unique=True),
    )


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


class DiscoveryLongitudinalSnapshot(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Patient-level memory generated from existing labs and cases."""

    __tablename__ = "discovery_longitudinal_snapshots"

    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False, index=True)
    patient_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("patients.id"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)


class DiscoveryInvestigationBranch(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "discovery_investigation_branches"

    case_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("discovery_cases.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[BranchLifecycleStatus] = mapped_column(
        Enum(BranchLifecycleStatus, native_enum=False, length=32),
        default=BranchLifecycleStatus.NOT_EVALUATED,
        nullable=False,
    )
    resolved_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    source_event_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    close_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (Index("uq_discovery_branches_case_code", "case_id", "code", unique=True),)


class DiscoveryEvidenceGap(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "discovery_evidence_gaps"

    case_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("discovery_cases.id"), nullable=False, index=True)
    branch_code: Mapped[str] = mapped_column(String(80), nullable=False)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    source_event_id: Mapped[str] = mapped_column(String(200), nullable=False)
    identity_key: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        Index("uq_discovery_gaps_identity", "case_id", "identity_key", unique=True),
        Index(
            "uq_discovery_gaps_active_code",
            "case_id",
            "branch_code",
            "code",
            unique=True,
            sqlite_where=active.is_(True),
            postgresql_where=active.is_(True),
        ),
    )


class DiscoveryWorkupItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "discovery_workup_items"

    case_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("discovery_cases.id"), nullable=False, index=True)
    test_code: Mapped[str] = mapped_column(String(80), nullable=False)
    raw_label: Mapped[str] = mapped_column(String(200), nullable=False)
    normalized_result: Mapped[str | None] = mapped_column(String(40), nullable=True)
    occurrence_date: Mapped[str | None] = mapped_column(String(40), nullable=True)
    source_event_id: Mapped[str] = mapped_column(String(200), nullable=False)
    identity_key: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (Index("uq_discovery_workup_identity", "case_id", "identity_key", unique=True),)


class DiscoveryEvidenceEdge(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "discovery_evidence_edges"

    case_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("discovery_cases.id"), nullable=False, index=True)
    branch_code: Mapped[str] = mapped_column(String(80), nullable=False)
    workup_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("discovery_workup_items.id"), nullable=True
    )
    relationship: Mapped[EvidenceRelationship] = mapped_column(
        Enum(EvidenceRelationship, native_enum=False, length=32), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    identity_key: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (Index("uq_discovery_evidence_identity", "case_id", "identity_key", unique=True),)


class DiscoveryMonitoringEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "discovery_monitoring_events"

    case_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("discovery_cases.id"), nullable=False, index=True)
    target: Mapped[str] = mapped_column(String(120), nullable=False)
    observation_time: Mapped[str] = mapped_column(String(40), nullable=False)
    outcome_kind: Mapped[MonitoringOutcomeKind] = mapped_column(
        Enum(MonitoringOutcomeKind, native_enum=False, length=32), nullable=False
    )
    exposure: Mapped[str | None] = mapped_column(String(80), nullable=True)
    adherence: Mapped[str | None] = mapped_column(String(80), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_event_id: Mapped[str] = mapped_column(String(200), nullable=False)
    identity_key: Mapped[str] = mapped_column(String(64), nullable=False)
    causal_claim: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (Index("uq_discovery_monitoring_identity", "case_id", "identity_key", unique=True),)
