import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class FeedbackCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str | None = None


class FeedbackRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    report_id: uuid.UUID
    rating: int
    comment: str | None = None
    created_at: datetime
