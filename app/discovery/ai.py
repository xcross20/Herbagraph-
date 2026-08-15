"""Discovery LLM hooks. Candidates and wording only — never clinical control."""

from __future__ import annotations

import logging
from typing import Any

from app.discovery.intake import ExtractedFact

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


def critic_allows(text: str) -> bool:
    lowered = (text or "").lower()
    return not any(phrase in lowered for phrase in _BANNED)


def merge_llm_facts(base: list[ExtractedFact], proposed: list[dict[str, Any]]) -> list[ExtractedFact]:
    """Keep only allow-listed names. Deterministic facts win on the same name."""
    have = {item.name for item in base}
    extra: list[ExtractedFact] = []
    for raw in proposed or []:
        name = str(raw.get("name") or "").strip().lower()
        value = str(raw.get("value") or "reported").strip()[:200]
        if name not in ALLOWED_FACT_NAMES or name in have or not value:
            continue
        extra.append(ExtractedFact(name=name, value=value, kind="symptom"))
        have.add(name)
    return [*base, *extra]


def pick_verbalization(fallback: str, candidate: str | None) -> str:
    if candidate and critic_allows(candidate) and 8 <= len(candidate) <= 1200:
        return candidate.strip()
    return fallback


def discovery_llm_ready() -> bool:
    """Live keys only. Fixture keys (`test-…`) must keep Discovery deterministic."""
    from app.pipeline.llm_client import llm_api_key, llm_configured

    if not llm_configured():
        return False
    key = (llm_api_key() or "").strip()
    return bool(key) and not key.startswith("test-")


def try_llm_json(system_prompt: str, user_prompt: str) -> dict[str, Any] | None:
    from app.pipeline.llm_client import parse_llm_json, sync_chat_json, create_sync_client

    if not discovery_llm_ready():
        return None
    try:
        client = create_sync_client()
        raw = sync_chat_json(
            client,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=800,
        )
        data = parse_llm_json(raw)
        return data if isinstance(data, dict) else None
    except Exception:
        logger.info("discovery LLM unavailable; using deterministic path")
        return None


def llm_extract_facts(text: str) -> list[dict[str, Any]]:
    data = try_llm_json(
        "Extract structured health facts as JSON {\"facts\":[{\"name\":\"\",\"value\":\"\"}]}. "
        "Use only these names: " + ", ".join(sorted(ALLOWED_FACT_NAMES)) + ". "
        "Do not diagnose. Do not invent labs.",
        text,
    )
    if not data:
        return []
    rows = data.get("facts")
    return rows if isinstance(rows, list) else []


def llm_verbalize(*, action_type: str, prompt: str | None, problem: str, audience: str) -> str | None:
    data = try_llm_json(
        "You verbalize a predetermined Discovery action. Do not change the action. "
        "Do not diagnose. Never say 'you have' a disease. JSON {\"message\":\"\"}.",
        f"audience={audience}\naction={action_type}\nrequired_question={prompt or ''}\n"
        f"problem={problem}\nInclude the required question if provided.",
    )
    if not data:
        return None
    message = data.get("message")
    return str(message) if message else None
