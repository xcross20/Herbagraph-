import uuid

from sqlalchemy import JSON, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import EvidenceLevel, EvidenceTier, InterventionCategory, SafetyRiskLevel
from app.models.mixins import GUID, TimestampMixin, UUIDPrimaryKeyMixin


class RecommendationReport(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "recommendation_reports"

    lab_report_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("lab_reports.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False)
    overall_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    model_version: Mapped[str] = mapped_column(String(30), nullable=False)
    executive_summary: Mapped[str] = mapped_column(Text, nullable=False)
    biomarker_summary: Mapped[dict] = mapped_column(JSON, default=dict)
    biomarker_interpretations: Mapped[list] = mapped_column(JSON, default=list)
    pathway_activations: Mapped[list] = mapped_column(JSON, default=list)
    biological_systems: Mapped[list] = mapped_column(JSON, default=list)
    clinician_questions: Mapped[list] = mapped_column(JSON, default=list)
    safety_summary: Mapped[dict] = mapped_column(JSON, default=dict)
    disclaimer: Mapped[str] = mapped_column(Text, nullable=False)

    lab_report: Mapped["LabReport"] = relationship(back_populates="reports")
    user: Mapped["User"] = relationship(back_populates="reports")
    recommendations: Mapped[list["Recommendation"]] = relationship(
        back_populates="report", cascade="all, delete-orphan", order_by="Recommendation.rank"
    )
    citations: Mapped[list["ReportCitation"]] = relationship(
        back_populates="report", cascade="all, delete-orphan"
    )


class Recommendation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "recommendations"

    report_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("recommendation_reports.id"), nullable=False
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    intervention_name: Mapped[str] = mapped_column(String(150), nullable=False)
    category: Mapped[InterventionCategory] = mapped_column(
        Enum(InterventionCategory, native_enum=False, length=30), nullable=False
    )
    mechanism: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_level: Mapped[EvidenceLevel] = mapped_column(
        Enum(EvidenceLevel, native_enum=False, length=20), nullable=False
    )
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    typical_dose: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    safety_risk: Mapped[SafetyRiskLevel] = mapped_column(
        Enum(SafetyRiskLevel, native_enum=False, length=20), nullable=False
    )
    safety_notes: Mapped[list[str]] = mapped_column(JSON, default=list)
    interactions: Mapped[list[str]] = mapped_column(JSON, default=list)
    is_regulated: Mapped[bool] = mapped_column(default=False)
    cited_study_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    cited_urls: Mapped[list[str]] = mapped_column(JSON, default=list)
    food_sources: Mapped[list | None] = mapped_column(JSON, nullable=True)
    limitations: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_tier: Mapped[EvidenceTier] = mapped_column(
        Enum(EvidenceTier, native_enum=False, length=30), default=EvidenceTier.RESEARCH_HYPOTHESIS
    )

    report: Mapped["RecommendationReport"] = relationship(back_populates="recommendations")


class ReportCitation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Denormalized snapshot of a citation as it appeared in a specific report."""

    __tablename__ = "report_citations"

    report_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("recommendation_reports.id"), nullable=False
    )
    external_id: Mapped[str] = mapped_column(String(50), nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    study_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    report: Mapped["RecommendationReport"] = relationship(back_populates="citations")
