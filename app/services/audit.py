"""Append-only audit trail for security and clinical traceability."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.audit import AuditEvent
from app.models.enums import AuditAction
from app.models.user import User


def _client_meta(request: Request | None) -> tuple[str | None, str | None]:
    if request is None:
        return None, None
    forwarded = request.headers.get("x-forwarded-for")
    ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else None)
    ua = request.headers.get("user-agent")
    return ip, ua[:300] if ua else None


def record_audit_event_sync(
    session: Session,
    *,
    action: AuditAction | str,
    summary: str,
    user_id: uuid.UUID | None = None,
    patient_id: uuid.UUID | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    detail: dict[str, Any] | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> AuditEvent:
    event = AuditEvent(
        user_id=user_id,
        patient_id=patient_id,
        action=action.value if isinstance(action, AuditAction) else str(action),
        resource_type=resource_type,
        resource_id=resource_id,
        summary=summary,
        detail=detail,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    session.add(event)
    session.flush()
    return event


async def record_audit_event(
    db: AsyncSession,
    *,
    action: AuditAction | str,
    summary: str,
    user: User | None = None,
    user_id: uuid.UUID | None = None,
    patient_id: uuid.UUID | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    detail: dict[str, Any] | None = None,
    request: Request | None = None,
) -> AuditEvent:
    ip, ua = _client_meta(request)
    effective_user_id = user_id or (user.id if user else None)
    event = AuditEvent(
        user_id=effective_user_id,
        patient_id=patient_id,
        action=action.value if isinstance(action, AuditAction) else str(action),
        resource_type=resource_type,
        resource_id=resource_id,
        summary=summary,
        detail=detail,
        ip_address=ip,
        user_agent=ua,
    )
    db.add(event)
    await db.flush()
    return event


async def list_audit_events(
    db: AsyncSession,
    user: User,
    *,
    limit: int = 50,
    patient_id: uuid.UUID | None = None,
) -> list[AuditEvent]:
    query = select(AuditEvent).where(AuditEvent.user_id == user.id)
    if patient_id is not None:
        query = query.where(AuditEvent.patient_id == patient_id)
    result = await db.execute(query.order_by(AuditEvent.created_at.desc()).limit(min(limit, 200)))
    return list(result.scalars().all())