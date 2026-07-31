"""Admin master password gate for the operator console."""

from __future__ import annotations

import secrets

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.config import get_settings
from app.core.security import create_admin_master_token

router = APIRouter(prefix="/admin", tags=["admin"])


class AdminMasterLogin(BaseModel):
    password: str = Field(min_length=8)


class AdminMasterTokenResponse(BaseModel):
    admin_token: str
    expires_in: int = 12 * 3600
    token_type: str = "bearer"


@router.post("/master-login", response_model=AdminMasterTokenResponse)
async def admin_master_login(payload: AdminMasterLogin) -> AdminMasterTokenResponse:
    """Exchange the operator master password for a short-lived admin API token."""
    settings = get_settings()
    configured = settings.admin_master_password.strip()
    if not configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin master password is not configured. Set ADMIN_MASTER_PASSWORD in the environment.",
        )
    if not secrets.compare_digest(payload.password, configured):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin password")

    return AdminMasterTokenResponse(admin_token=create_admin_master_token())