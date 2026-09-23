"""Unauthenticated metabolic wedge endpoints. No PHI persistence."""

from __future__ import annotations

import time
from collections import defaultdict

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.discovery.intent import classify_opening_door
from app.pipeline.stack_check import evaluate_stack

router = APIRouter(prefix="/public", tags=["public"])

_HITS: dict[str, list[float]] = defaultdict(list)
_WINDOW = 60.0
_MAX = 20


def _rate_limit(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    bucket = [stamp for stamp in _HITS[ip] if now - stamp < _WINDOW]
    if len(bucket) >= _MAX:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Slow down and try again shortly.")
    bucket.append(now)
    _HITS[ip] = bucket


class PublicLabRow(BaseModel):
    name: str
    value: float
    unit: str | None = None


class StackCheckRequest(BaseModel):
    labs: list[PublicLabRow] = Field(default_factory=list)
    stack: list[str] = Field(default_factory=list)
    medications: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    ranking_mode: str = "consumer"


class OpeningDoorRequest(BaseModel):
    text: str


@router.post("/stack-check")
async def public_stack_check(payload: StackCheckRequest, request: Request) -> dict:
    _rate_limit(request)
    if len(payload.stack) > 12 or len(payload.labs) > 30:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Too many items for a public check.")
    mode = payload.ranking_mode if payload.ranking_mode in {"consumer", "clinician"} else "consumer"
    return evaluate_stack(
        labs=[row.model_dump() for row in payload.labs],
        stack=payload.stack,
        medications=payload.medications,
        conditions=payload.conditions,
        ranking_mode=mode,
    )


@router.post("/opening-door")
async def public_opening_door(payload: OpeningDoorRequest, request: Request) -> dict:
    _rate_limit(request)
    return {"door": classify_opening_door(payload.text), "text": payload.text}
