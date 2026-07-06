import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PatientCreate(BaseModel):
    age: int | None = None
    biological_sex: str | None = None


class PatientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    age: int | None = None
    biological_sex: str | None = None
    created_at: datetime
