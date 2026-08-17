"""Deterministic mutation identities (ADR-MVP-003)."""

from __future__ import annotations

import hashlib
import uuid

from app.discovery.coverage_catalog import normalize_label


def finding_identity_key(
    *,
    case_id: uuid.UUID,
    name: str,
    value: str | None,
    source_event_id: str,
) -> str:
    material = "|".join(
        (
            str(case_id),
            normalize_label(name),
            normalize_label(value or ""),
            source_event_id,
        )
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def finding_source_event_id(*, source: str, name: str, value: str | None) -> str:
    return f"{source}:{normalize_label(name)}:{normalize_label(value or '')}"


def gap_identity_key(
    *,
    case_id: uuid.UUID,
    branch_code: str,
    gap_code: str,
    source_event_id: str,
) -> str:
    material = "|".join((str(case_id), branch_code, gap_code, source_event_id))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def evidence_identity_key(
    *,
    case_id: uuid.UUID,
    branch_code: str,
    workup_key: str,
    relationship: str,
    version: int,
) -> str:
    material = "|".join((str(case_id), branch_code, workup_key, relationship, str(version)))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()
