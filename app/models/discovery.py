"""Persistent Guided Discovery Case, Finding, and Hypothesis rows."""

from __future__ import annotations

import uuid

from sqlalchemy import Enum, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import DiscoveryCaseStatus, DiscoveryFindingKind, DiscoveryHypothesisStatus
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

    findings: Mapped[list["DiscoveryFinding"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )
    hypotheses: Mapped[list["DiscoveryHypothesis"]] = relationship(
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
