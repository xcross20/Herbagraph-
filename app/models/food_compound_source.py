import uuid

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import Richness
from app.models.mixins import GUID, TimestampMixin, UUIDPrimaryKeyMixin


class FoodCompoundSource(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "food_compound_sources"

    food_intervention_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("interventions.id"), nullable=False
    )
    compound_intervention_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("interventions.id"), nullable=False
    )
    richness: Mapped[Richness] = mapped_column(Enum(Richness, native_enum=False, length=20), nullable=False)
    typical_serving: Mapped[str | None] = mapped_column(String(150), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    food_intervention: Mapped["Intervention"] = relationship(foreign_keys=[food_intervention_id])
    compound_intervention: Mapped["Intervention"] = relationship(foreign_keys=[compound_intervention_id])
