from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Pathway(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "pathways"

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    pathway_type: Mapped[str] = mapped_column(String(20), nullable=False, default="signaling")
