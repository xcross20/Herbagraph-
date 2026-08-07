import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import PatientContextSource, PatientContextType


class PatientContextCreate(BaseModel):
    context_type: PatientContextType
    name: str = Field(min_length=1, max_length=200)
    value: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    active: bool = True
    source: PatientContextSource = PatientContextSource.USER


class PatientContextUpdate(BaseModel):
    context_type: PatientContextType | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)
    value: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    active: bool | None = None


class PatientContextRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    patient_id: uuid.UUID
    context_type: PatientContextType
    name: str
    value: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    active: bool
    source: PatientContextSource
    created_at: datetime


class PatientConditionsReplace(BaseModel):
    """Replace active condition toggles for a patient (matrix + Other free text)."""

    conditions: list[str] = Field(default_factory=list, max_length=200)

