"""Central Case authorization. Endpoints must not roll their own owner checks."""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.discovery.service import get_owned_case
from app.models.discovery import DiscoveryCase
from app.models.enums import DiscoveryCaseStatus


async def require_owned_case(db: AsyncSession, case_id: uuid.UUID, user_id: uuid.UUID) -> DiscoveryCase:
    case = await get_owned_case(db, case_id, user_id)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    return case


def require_open_case(case: DiscoveryCase) -> DiscoveryCase:
    if case.status == DiscoveryCaseStatus.CLOSED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This conversation was deleted. Start a new one.",
        )
    return case
