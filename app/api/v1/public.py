"""Unauthenticated Stack Check. Nothing from the request is stored or logged."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator

from app.api.public_rate_limit import enforce_public_rate_limit, get_public_rate_store
from app.pipeline.stack_verdicts import evaluate_stack

router = APIRouter(prefix="/public", tags=["public"])

DISCLAIMER = "Not a diagnosis. Nothing from this check is stored."
_ITEM_MAX = 80


class PublicLabRow(BaseModel):
    name: str = Field(min_length=1, max_length=_ITEM_MAX)
    value: float = Field(gt=-1_000_000, lt=1_000_000)
    unit: str | None = Field(default=None, max_length=40)


class StackCheckRequest(BaseModel):
    labs: list[PublicLabRow] = Field(default_factory=list, max_length=30)
    stack: list[str] = Field(min_length=1, max_length=12)
    medications: list[str] | None = Field(default=None, max_length=12)
    conditions: list[str] | None = Field(default=None, max_length=12)

    @field_validator("stack", "medications", "conditions")
    @classmethod
    def items_are_short(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        if any(not item.strip() or len(item) > _ITEM_MAX for item in value):
            raise ValueError("each item must be a short name")
        return [item.strip() for item in value]


def _limited(request: Request, store=Depends(get_public_rate_store)) -> None:
    enforce_public_rate_limit(request, store)


@router.post("/stack-check")
async def public_stack_check(payload: StackCheckRequest, _: None = Depends(_limited)) -> dict:
    if not payload.labs:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Enter at least one lab value.")
    decision = evaluate_stack(
        labs=[row.model_dump() for row in payload.labs],
        stack=payload.stack,
        medications=payload.medications,
        conditions=payload.conditions,
    )
    return {"verdicts": decision["verdicts"], "disclaimer": DISCLAIMER}
