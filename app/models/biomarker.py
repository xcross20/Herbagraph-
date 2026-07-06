from sqlalchemy import Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Biomarker(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "biomarkers"

    canonical_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_unit: Mapped[str | None] = mapped_column(String(30), nullable=True)
    reference_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    reference_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    optimal_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    optimal_high: Mapped[float | None] = mapped_column(Float, nullable=True)
