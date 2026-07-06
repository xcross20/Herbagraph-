import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import GUID, TimestampMixin, UUIDPrimaryKeyMixin


class Feedback(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """User feedback on a specific RecommendationReport (Phase 4 infrastructure)."""

    __tablename__ = "feedback"
    __table_args__ = (CheckConstraint("rating >= 1 AND rating <= 5", name="feedback_rating_range"),)

    report_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("recommendation_reports.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    report: Mapped["RecommendationReport"] = relationship(back_populates="feedback")
