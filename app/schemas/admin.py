"""Admin console schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import UserRole


class AdminUserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str | None = None
    is_active: bool
    is_verified: bool
    auth_provider: str
    role: UserRole
    clinic_name: str | None = None
    created_at: datetime
    patient_count: int = 0
    lab_report_count: int = 0
    report_count: int = 0


class AdminUserListRead(BaseModel):
    total: int
    items: list[AdminUserRead]


class AdminUserUpdate(BaseModel):
    is_active: bool | None = None
    is_verified: bool | None = None
    role: UserRole | None = None
    full_name: str | None = None
    clinic_name: str | None = None


class AdminUserDeleteResult(BaseModel):
    deleted: bool
    user_id: uuid.UUID
    email: str
    note: str | None = None