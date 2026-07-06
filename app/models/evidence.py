import uuid

from sqlalchemy import Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import EvidenceLevel, StudySource, StudyType
from app.models.mixins import GUID, TimestampMixin, UUIDPrimaryKeyMixin


class EvidenceClaim(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "evidence_claims"

    intervention_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("interventions.id"), nullable=False
    )
    biomarker_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    pathway_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    effect: Mapped[str] = mapped_column(String(50), nullable=False)
    evidence_level: Mapped[EvidenceLevel] = mapped_column(
        Enum(EvidenceLevel, native_enum=False, length=20), nullable=False
    )
    pmid: Mapped[str | None] = mapped_column(String(30), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    intervention: Mapped["Intervention"] = relationship(back_populates="evidence_claims")


class Citation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "citations"

    external_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    source: Mapped[StudySource] = mapped_column(
        Enum(StudySource, native_enum=False, length=20), nullable=False
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    study_type: Mapped[StudyType | None] = mapped_column(
        Enum(StudyType, native_enum=False, length=30), nullable=True
    )
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
