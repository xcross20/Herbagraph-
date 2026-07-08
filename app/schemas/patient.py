import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class PatientCreate(BaseModel):
    display_name: str = Field(default="Patient", min_length=1, max_length=120)
    date_of_birth: date | None = None
    age: int | None = None
    biological_sex: str | None = None
    notes: str | None = None


class PatientUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    date_of_birth: date | None = None
    age: int | None = None
    biological_sex: str | None = None
    notes: str | None = None


class PatientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    display_name: str
    date_of_birth: date | None = None
    age: int | None = None
    biological_sex: str | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime
