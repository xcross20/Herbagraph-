import uuid

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import FlagSeverity, SafetyRiskLevel
from app.models.mixins import GUID, TimestampMixin, UUIDPrimaryKeyMixin


class SafetyFlag(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "safety_flags"

    intervention_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("interventions.id"), nullable=False
    )
    condition: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[FlagSeverity] = mapped_column(
        Enum(FlagSeverity, native_enum=False, length=20), nullable=False
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    intervention: Mapped["Intervention"] = relationship(back_populates="safety_flags")


class DrugInteraction(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "drug_interactions"

    intervention_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("interventions.id"), nullable=False
    )
    drug_name: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[SafetyRiskLevel] = mapped_column(
        Enum(SafetyRiskLevel, native_enum=False, length=20), nullable=False
    )
    mechanism: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    intervention: Mapped["Intervention"] = relationship(back_populates="drug_interactions")
