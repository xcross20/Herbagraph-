import uuid
from datetime import date

from sqlalchemy import Boolean, Date, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import PatientContextSource, PatientContextType
from app.models.mixins import GUID, TimestampMixin, UUIDPrimaryKeyMixin


class PatientContext(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "patient_context"

    patient_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("patients.id"), nullable=False, index=True)
    context_type: Mapped[PatientContextType] = mapped_column(
        Enum(PatientContextType, native_enum=False, length=30), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    source: Mapped[PatientContextSource] = mapped_column(
        Enum(PatientContextSource, native_enum=False, length=50),
        default=PatientContextSource.USER,
        nullable=False,
    )

    patient: Mapped["Patient"] = relationship(back_populates="context_items")