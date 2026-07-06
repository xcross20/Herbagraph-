from sqlalchemy import Boolean, Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import InterventionCategory
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Intervention(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "interventions"

    name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    category: Mapped[InterventionCategory] = mapped_column(
        Enum(InterventionCategory, native_enum=False, length=30), nullable=False
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    mechanism: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_regulated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    regulation_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    evidence_claims: Mapped[list["EvidenceClaim"]] = relationship(
        back_populates="intervention", cascade="all, delete-orphan"
    )
    safety_flags: Mapped[list["SafetyFlag"]] = relationship(
        back_populates="intervention", cascade="all, delete-orphan"
    )
    drug_interactions: Mapped[list["DrugInteraction"]] = relationship(
        back_populates="intervention", cascade="all, delete-orphan"
    )
