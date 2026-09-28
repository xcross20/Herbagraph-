"""Address counter for the public Stack Check. No labs and no medications."""

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PublicRateBucket(Base):
    __tablename__ = "public_rate_buckets"

    bucket_key: Mapped[str] = mapped_column(String(200), primary_key=True)
    hit_count: Mapped[int] = mapped_column(Integer, nullable=False)
    window_started_epoch: Mapped[int] = mapped_column(Integer, nullable=False)
