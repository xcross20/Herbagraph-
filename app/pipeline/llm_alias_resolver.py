"""LLM-assisted alias resolution for unresolved abnormal lab names (IMP-053).

Used after deterministic alias maps fail. Never invents biomarkers outside the
catalog + optional custom profile. Safe no-op without API keys or when mocked.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Iterable

from app.knowledge_graph.biomarker_catalog import REFERENCE_DATA
from app.pipeline.llm_client import (
    async_chat_json_with_fallback,
    llm_configured,
    llm_provider,
    parse_llm_json,
)
from app.pipeline.user_biomarker_profile import resolve_canonical_name

logger = logging.getLogger(__name__)

_MOCK_ENV = "HERBAGRAPH_MOCK_LLM"
_MAX_CATALOG_HINTS = 80


def _catalog_names() -> list[str]:
    return sorted(REFERENCE_DATA.keys())


def _clean(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip())


def fuzzy_catalog_candidates(raw_name: str, *, limit: int = 12) -> list[str]:
    """Cheap lexical shortlist for the LLM prompt (no network)."""
    tokens = set(re.findall(r"[a-z0-9]+", raw_name.lower()))
    if not tokens:
        return []
    scored: list[tuple[int, str]] = []
    for name in _catalog_names():
        name_tokens = set(re.findall(r"[a-z0-9]+", name.lower()))
        overlap = len(tokens & name_tokens)
        if overlap:
            scored.append((overlap, name))
        elif any(t in name.lower() for t in tokens if len(t) >= 4):
            scored.append((1, name))
    scored.sort(key=lambda row: (-row[0], row[1]))
    return [name for _, name in scored[:limit]]


async def resolve_aliases_with_llm(
    unresolved_names: Iterable[str],
    *,
    custom_biomarkers: list[dict] | None = None,
) -> dict[str, str]:
    """Map raw unresolved names → catalog canonical names.

    Returns only mappings that validate against the catalog.
    """
    unique: list[str] = []
    seen: set[str] = set()
    for raw in unresolved_names:
        cleaned = _clean(str(raw or ""))
        if not cleaned or cleaned.lower() in seen:
            continue
        if resolve_canonical_name(cleaned, custom_biomarkers):
            continue
        seen.add(cleaned.lower())
        unique.append(cleaned)
    if not unique:
        return {}

    mock = (
        os.environ.get(_MOCK_ENV) == "1"
        or os.environ.get("OPENAI_API_KEY") == "test-openai-api-key"
        or not llm_configured()
    )
    if mock:
        return _mock_resolve(unique)

    payload = []
    for name in unique[:25]:
        payload.append(
            {
                "raw": name,
                "candidates": fuzzy_catalog_candidates(name, limit=10),
            }
        )

    catalog_sample = _catalog_names()[:_MAX_CATALOG_HINTS]
    system = (
        "You map messy lab portal test names to HerbaGraph catalog biomarker names. "
        "Only choose from candidates or the catalog sample. "
        "Return JSON object mapping raw names to canonical names. "
        "Use null when unsure. Never invent biomarkers."
    )
    user = json.dumps(
        {
            "items": payload,
            "catalog_sample": catalog_sample,
            "instructions": 'Prefer candidates. Output {"mappings": {raw: canonical|null}}',
        }
    )

    try:
        text, _fallback = await async_chat_json_with_fallback(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=1200,
        )
        raw_response = parse_llm_json(text)
    except Exception as exc:  # noqa: BLE001 — alias assist must never break normalize
        logger.warning("LLM alias resolve failed (%s): %s", llm_provider(), exc)
        return _mock_resolve(unique)

    return _validate_mappings(raw_response, unique, custom_biomarkers)


def _extract_mappings_dict(raw_response: object) -> dict:
    if isinstance(raw_response, dict):
        if isinstance(raw_response.get("mappings"), dict):
            return raw_response["mappings"]
        return {k: v for k, v in raw_response.items() if k != "mappings"}
    return {}


def _validate_mappings(
    raw_response: object,
    requested: list[str],
    custom_biomarkers: list[dict] | None,
) -> dict[str, str]:
    mappings = _extract_mappings_dict(raw_response)
    out: dict[str, str] = {}
    requested_lower = {r.lower(): r for r in requested}
    for raw_key, canonical in mappings.items():
        if canonical is None or canonical == "" or str(canonical).lower() == "null":
            continue
        raw_orig = requested_lower.get(str(raw_key).lower(), str(raw_key))
        candidate = str(canonical).strip()
        if candidate in REFERENCE_DATA:
            out[raw_orig] = candidate
            continue
        resolved = resolve_canonical_name(candidate, custom_biomarkers)
        if resolved and resolved in REFERENCE_DATA:
            out[raw_orig] = resolved
    return out


def _mock_resolve(names: list[str]) -> dict[str, str]:
    """Deterministic offline mapping for CI / missing keys."""
    out: dict[str, str] = {}
    heuristics = {
        "fe total": "Iron",
        "iron total": "Iron",
        "fe serum": "Iron",
        "hgb": "Hemoglobin",
        "hb a1c": "HbA1c",
        "vit d 25": "Vitamin D",
        "25 oh d": "Vitamin D",
        "tsh 3rd": "TSH",
        "crp hs": "CRP",
        "hs crp": "CRP",
        "ldl c": "LDL",
        "hdl c": "HDL",
        "trig": "Triglycerides",
        "triglyceride": "Triglycerides",
    }
    for name in names:
        key = re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()
        if key in heuristics and heuristics[key] in REFERENCE_DATA:
            out[name] = heuristics[key]
            continue
        candidates = fuzzy_catalog_candidates(name, limit=1)
        if candidates:
            tokens = set(re.findall(r"[a-z0-9]+", key))
            cand_tokens = set(re.findall(r"[a-z0-9]+", candidates[0].lower()))
            if len(tokens & cand_tokens) >= 1 and any(len(t) >= 3 for t in tokens & cand_tokens):
                out[name] = candidates[0]
    return out


def apply_alias_map_to_parsed(parsed_results: list, alias_map: dict[str, str]) -> list:
    """Return parsed results with raw_test_name rewritten when mapped."""
    if not alias_map:
        return list(parsed_results)
    lower_map = {k.lower(): v for k, v in alias_map.items()}
    updated = []
    for row in parsed_results:
        raw = getattr(row, "raw_test_name", None) or ""
        hit = lower_map.get(raw.lower())
        if hit:
            updated.append(row.model_copy(update={"raw_test_name": hit}))
        else:
            updated.append(row)
    return updated
