import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import GUID, TimestampMixin, UUIDPrimaryKeyMixin


class ReportFeedback(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Clinician-facing structured feedback on a generated report."""

    __tablename__ = "report_feedback"
    __table_args__ = (
        CheckConstraint(
            "clinical_usefulness_score >= 1 AND clinical_usefulness_score <= 5",
            name="report_feedback_usefulness_range",
        ),
        CheckConstraint(
            "trust_score IS NULL OR (trust_score >= 1 AND trust_score <= 5)",
            name="report_feedback_trust_range",
        ),
    )

    report_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("recommendation_reports.id"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False, index=True)
    clinical_usefulness_score: Mapped[int] = mapped_column(Integer, nullable=False)
    reasoning_agreement: Mapped[str] = mapped_column(String(20), nullable=False)
    trust_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_time_saved_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    most_useful_section: Mapped[str | None] = mapped_column(String(80), nullable=True)
    least_useful_section: Mapped[str | None] = mapped_column(String(80), nullable=True)
    patient_encounter_comfort: Mapped[str | None] = mapped_column(String(30), nullable=True)
    would_use_again: Mapped[str | None] = mapped_column(String(20), nullable=True)
    safety_concerns: Mapped[str | None] = mapped_column(Text, nullable=True)
    free_text_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)

    report: Mapped["RecommendationReport"] = relationship(back_populates="report_feedback")


class ValidationEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Internal product analytics — section opens, citation clicks, downloads, etc."""

    __tablename__ = "validation_events"

    report_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("recommendation_reports.id"), nullable=True, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    section_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)