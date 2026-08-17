"""Coverage ontology tables. Separate from Discovery case state."""

from __future__ import annotations

import uuid

from sqlalchemy import Enum, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.enums import CoverageRelation
from app.models.mixins import GUID, TimestampMixin, UUIDPrimaryKeyMixin


class CoverageDiagnosticTest(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "coverage_diagnostic_tests"

    code: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    canonical_name: Mapped[str] = mapped_column(String(200), nullable=False)
    modality: Mapped[str] = mapped_column(String(40), nullable=False)
    specialty: Mapped[str] = mapped_column(String(40), nullable=False, default="general")
    loinc_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class CoverageTestAlias(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "coverage_test_aliases"
    __table_args__ = (UniqueConstraint("test_id", "alias", name="uq_coverage_alias"),)

    test_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("coverage_diagnostic_tests.id"), nullable=False, index=True
    )
    alias: Mapped[str] = mapped_column(String(200), nullable=False)
    vendor: Mapped[str | None] = mapped_column(String(80), nullable=True)


class CoverageTestProtocol(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "coverage_test_protocols"

    test_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("coverage_diagnostic_tests.id"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class CoverageInvestigationConcept(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "coverage_investigation_concepts"

    code: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class CoverageTestRelation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "coverage_test_relations"

    test_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("coverage_diagnostic_tests.id"), nullable=False, index=True
    )
    protocol_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("coverage_test_protocols.id"), nullable=True
    )
    investigation_concept_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("coverage_investigation_concepts.id"), nullable=False, index=True
    )
    relation: Mapped[CoverageRelation] = mapped_column(
        Enum(CoverageRelation, native_enum=False, length=40), nullable=False
    )
    coverage_strength: Mapped[float] = mapped_column(Float, nullable=False, default=0.8)
    sensitivity_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    limitations: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_source: Mapped[str | None] = mapped_column(String(160), nullable=True)


class CoverageTestFollowup(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "coverage_test_followups"

    from_test_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("coverage_diagnostic_tests.id"), nullable=False
    )
    to_test_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("coverage_diagnostic_tests.id"), nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    condition: Mapped[str | None] = mapped_column(String(160), nullable=True)
