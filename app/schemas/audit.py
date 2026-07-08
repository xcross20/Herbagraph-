import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID | None = None
    patient_id: uuid.UUID | None = None
    action: str
    resource_type: str | None = None
    resource_id: str | None = None
    summary: str
    detail: dict | None = None
    created_at: datetime