import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import GUID, TimestampMixin, UUIDPrimaryKeyMixin


class Patient(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A patient profile owned by a user account.

    Supports pseudonymous display names (e.g. Self, Patient A). Labs, analyses,
    and reports can be scoped to a patient for longitudinal tracking.
    """

    __tablename__ = "patients"

    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("organizations.id"), nullable=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False, default="Patient")
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    biological_sex: Mapped[str | None] = mapped_column(String(10), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship(back_populates="patients")
    lab_reports: Mapped[list["LabReport"]] = relationship(back_populates="patient")
    context_items: Mapped[list["PatientContext"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )
