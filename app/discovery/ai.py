"""Discovery LLM hooks. Candidates and wording only — never clinical control."""

from __future__ import annotations

import logging
import re
from typing import Any

from app.discovery.intake import ExtractedFact
from app.discovery.safety import SAFETY_ENGINE_RULE

logger = logging.getLogger(__name__)

ALLOWED_FACT_NAMES = frozenset(
    {
        "burning sensation",
        "paresthesia",
        "numbness",
        "temperature sensation",
        "location",
        "distribution",
        "laterality",
        "timing",
        "duration",
        "onset",
        "weakness",
        "sphincter change",
        "claimed normal labs",
        "emg testing",
        "prior_workup",
        "medications",
        "fever",
        "vomiting",
        "jaundice",
        "severity",
        "chronology",
        "trajectory",
        "abdominal_pain",
        "chest_pain",
        "dyspnea",
        "syncope",
        "sweating",
        "patient_interpretation",
    }
)

_BANNED = (
    "you have small-fiber",
    "you have neuropathy",
    "you have diabetes",
    "this confirms",
    "this strongly suggests",
    "diagnosed with",
)

DENIED_CONCEPTS = (
    "trigeminal neuralgia",
    "neuropathy",
    "small-fiber",
    "diabetes",
    "sepsis",
    "cholecystitis",
    "appendicitis",
    "cancer",
    "tumor",
    "stroke",
    "diagnosis",
    "you have",
)


def is_denied_concept(text: str) -> bool:
    """Whole-token / whole-phrase match. 'gallbladder' is not 'bladder'; 'tumorigenesis' is not 'tumor'."""
    blob = (text or "").lower()
    for token in DENIED_CONCEPTS:
        if re.search(rf"(?<![\w]){re.escape(token)}(?![\w])", blob):
            return True
    return False


_REPEATABLE_PREFIXES = ("patient_interpretation", "timeline", "prior_workup")


def _is_repeatable(name: str) -> bool:
    return any(name == prefix or name.startswith(prefix + "_") for prefix in _REPEATABLE_PREFIXES)


def _unique_fact_name(name: str, have: set[str]) -> str | None:
    if name not in have:
        return name
    if not _is_repeatable(name):
        return None
    stem = next(prefix for prefix in _REPEATABLE_PREFIXES if name == prefix or name.startswith(prefix + "_"))
    index = 2
    while f"{stem}_{index}" in have:
        index += 1
    return f"{stem}_{index}"


def _name_is_allowed(name: str, *, allow_open: bool) -> bool:
    if name in ALLOWED_FACT_NAMES or _is_repeatable(name):
        return True
    if allow_open and not is_denied_concept(name) and 3 <= len(name) <= 180:
        return True
    return False


def critic_allows(text: str) -> bool:
    lowered = (text or "").lower()
    return not any(phrase in lowered for phrase in _BANNED)


def merge_llm_facts(
    base: list[ExtractedFact],
    proposed: list[dict[str, Any]],
    *,
    allow_open: bool = False,
) -> list[ExtractedFact]:
    """Keep allow-listed names, or open reported concepts that are not diagnoses."""
    have = {item.name for item in base}
    extra: list[ExtractedFact] = []
    for raw in proposed or []:
        name = str(raw.get("name") or "").strip().lower()
        value = str(raw.get("value") or "reported").strip()[:400]
        kind = str(raw.get("kind") or "symptom")
        if not name or not value:
            continue
        keyed = _unique_fact_name(name, have)
        if keyed is None or not _name_is_allowed(keyed, allow_open=allow_open):
            continue
        if kind not in {"symptom", "context", "assessment"}:
            kind = "symptom"
        extra.append(ExtractedFact(name=keyed, value=value, kind=kind))
        have.add(keyed)
    return [*base, *extra]


def pick_verbalization(fallback: str, candidate: str | None) -> str:
    if candidate and critic_allows(candidate) and 8 <= len(candidate) <= 1200:
        return candidate.strip()
    return fallback


def discovery_llm_ready() -> bool:
    """Live keys only. Pytest and fixture keys (`test-…`) stay deterministic."""
    import os

    from app.pipeline.llm_client import llm_api_key, llm_configured

    if os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    if not llm_configured():
        return False
    key = (llm_api_key() or "").strip()
    return bool(key) and not key.startswith("test-")


async def try_llm_json(
    system_prompt: str, user_prompt: str, *, max_tokens: int = 800
) -> dict[str, Any] | None:
    from app.pipeline.llm_client import async_chat_json, create_async_client, parse_llm_json

    if not discovery_llm_ready():
        return None
    client = create_async_client()
    try:
        raw = await async_chat_json(
            client,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max_tokens,
        )
        data = parse_llm_json(raw)
        return data if isinstance(data, dict) else None
    except Exception:
        logger.info("discovery LLM unavailable; using deterministic path")
        return None
    finally:
        await client.close()


async def llm_extract_facts(text: str) -> list[dict[str, Any]]:
    data = await try_llm_json(
        "Extract structured health facts as JSON {\"facts\":[{\"name\":\"\",\"value\":\"\"}]}. "
        "Use only these names: " + ", ".join(sorted(ALLOWED_FACT_NAMES)) + ". "
        "Do not diagnose. Do not invent labs.",
        text,
    )
    if not data:
        return []
    rows = data.get("facts")
    return rows if isinstance(rows, list) else []


async def llm_verbalize(*, action_type: str, prompt: str | None, problem: str, audience: str) -> str | None:
    data = await try_llm_json(
        "You verbalize a predetermined Discovery action. Do not change the action. "
        "Do not diagnose. Never say 'you have' a disease. "
        "Do not name inferred conditions. JSON {\"message\":\"\"}. "
        + SAFETY_ENGINE_RULE,
        f"audience={audience}\naction={action_type}\nrequired_question={prompt or ''}\n"
        f"problem={problem}\nInclude the required question if provided.",
    )
    if not data:
        return None
    message = data.get("message")
    return str(message) if message else None
