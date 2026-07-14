import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

from app.models.enums import UserRole

_UPPERCASE_RE = re.compile(r"[A-Z]")
_DIGIT_RE = re.compile(r"\d")


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    access_code: str | None = None
    full_name: str | None = None
    role: UserRole = UserRole.INDIVIDUAL
    clinic_name: str | None = None

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not _UPPERCASE_RE.search(value):
            raise ValueError("Password must contain at least one uppercase letter")
        if not _DIGIT_RE.search(value):
            raise ValueError("Password must contain at least one digit")
        return value


class SignupAccessVerify(BaseModel):
    email: EmailStr
    access_code: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str | None = None
    is_active: bool
    is_verified: bool
    auth_provider: str = "local"
    role: UserRole
    clinic_name: str | None = None
    created_at: datetime


class AccessCodeOnlyVerify(BaseModel):
    access_code: str


class SignupApprovalTokenRead(BaseModel):
    approval_token: str
    expires_in: int = 900


class AuthConfigRead(BaseModel):
    auth_provider: str
    supabase_url: str | None = None
    supabase_anon_key: str | None = None
    require_email_verification: bool
    allow_guest_auth: bool
    signup_access_required: bool = False
    google_oauth_enabled: bool = False


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class CustomBiomarkerRead(BaseModel):
    canonical_name: str
    aliases: list[str] = []
    unit: str | None = None
    reference_low: float | None = None
    reference_high: float | None = None
    category: str | None = None
    source: str | None = None
    added_at: str | None = None


class HealthProfileUpdate(BaseModel):
    age_range: str | None = None
    biological_sex: str | None = None
    health_goals: list[str] | None = None
    current_medications: list[str] | None = None
    current_supplements: list[str] | None = None
    known_conditions: list[str] | None = None
    custom_biomarkers: list[CustomBiomarkerRead] | None = None


class HealthProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    age_range: str | None = None
    biological_sex: str | None = None
    health_goals: list[str] = []
    current_medications: list[str] = []
    current_supplements: list[str] = []
    known_conditions: list[str] = []
    custom_biomarkers: list[dict] = []