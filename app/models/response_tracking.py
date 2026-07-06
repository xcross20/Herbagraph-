import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import GUID, TimestampMixin, UUIDPrimaryKeyMixin


class ResponseTracking(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Links a baseline LabReport to a later follow-up LabReport for the same
    intervention, so the pipeline can answer "did this biological system improve?"
    rather than only "here's information about this system."

    Deliberately minimal: this is a comparison of two lab snapshots over time, not a
    causal claim. See app/pipeline/response_analysis.py for how the comparison is
    computed (pure arithmetic against each biomarker's optimal range -- no ML, no
    LLM call) and DISCLAIMER in that module for the non-causality language every
    response report carries.
    """

    __tablename__ = "response_tracking"

    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False)
    patient_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("patients.id"), nullable=True)
    intervention_name: Mapped[str] = mapped_column(String(150), nullable=False)
    baseline_lab_report_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("lab_reports.id"), nullable=False
    )
    follow_up_lab_report_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("lab_reports.id"), nullable=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship()
    patient: Mapped["Patient | None"] = relationship()
    baseline_lab_report: Mapped["LabReport"] = relationship(foreign_keys=[baseline_lab_report_id])
    follow_up_lab_report: Mapped["LabReport | None"] = relationship(foreign_keys=[follow_up_lab_report_id])
