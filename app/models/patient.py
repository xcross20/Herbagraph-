import uuid

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import GUID, TimestampMixin, UUIDPrimaryKeyMixin


class Patient(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A patient managed by a clinician/clinic User account (Phase 4 infrastructure).

    Deliberately carries no name or other direct identifier -- a Patient is just a
    random UUID plus non-identifying demographics, the same "random ID, no PII"
    principle already used for HealthProfile. Individual (non-clinician) users don't
    need this at all: their own LabReports link directly to their User row, exactly
    as before -- `LabReport.patient_id` is optional and only used in clinic mode.
    """

    __tablename__ = "patients"

    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    biological_sex: Mapped[str | None] = mapped_column(String(10), nullable=True)

    user: Mapped["User"] = relationship(back_populates="patients")
    lab_reports: Mapped[list["LabReport"]] = relationship(back_populates="patient")
