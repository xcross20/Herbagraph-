"""Shared LLM client factory — OpenAI or MiniMax (OpenAI-compatible API)."""

from __future__ import annotations

import json
import re
from typing import Any

from openai import APIConnectionError, APITimeoutError, AsyncOpenAI, OpenAI

from app.config import get_settings

_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)

DEFAULT_MINIMAX_BASE_URL = "https://api.minimax.io/v1"


def _settings():
    return get_settings()


def llm_provider() -> str:
    return (_settings().llm_provider or "openai").strip().lower()


def llm_api_key() -> str:
    cfg = _settings()
    if llm_provider() == "minimax":
        return cfg.minimax_api_key or cfg.openai_api_key
    return cfg.openai_api_key


def llm_base_url() -> str | None:
    cfg = _settings()
    if cfg.llm_base_url:
        return cfg.llm_base_url
    if llm_provider() == "minimax":
        return DEFAULT_MINIMAX_BASE_URL
    return None


def llm_configured() -> bool:
    return bool(llm_api_key())


def minimax_extra_body() -> dict[str, Any]:
    """Separate M2.x thinking traces from the answer payload when supported."""
    if llm_provider() == "minimax":
        return {"reasoning_split": True}
    return {}


def extract_llm_text(content: str | None) -> str:
    """Return user-facing model text, stripping MiniMax thinking blocks and markdown fences."""
    if not content:
        return ""
    text = _THINK_BLOCK_RE.sub("", content).strip()
    fence = _JSON_FENCE_RE.search(text)
    if fence:
        return fence.group(1).strip()
    return text


def parse_llm_json(content: str | None) -> dict:
    text = extract_llm_text(content)
    if not text:
        raise ValueError("LLM returned empty content")
    return json.loads(text)


def create_sync_client() -> OpenAI:
    api_key = llm_api_key()
    if not api_key:
        provider = llm_provider()
        key_name = "MINIMAX_API_KEY" if provider == "minimax" else "OPENAI_API_KEY"
        raise RuntimeError(f"{key_name} is not configured")
    base_url = llm_base_url()
    if base_url:
        return OpenAI(api_key=api_key, base_url=base_url)
    return OpenAI(api_key=api_key)


def create_async_client() -> AsyncOpenAI:
    api_key = llm_api_key()
    if not api_key:
        provider = llm_provider()
        key_name = "MINIMAX_API_KEY" if provider == "minimax" else "OPENAI_API_KEY"
        raise RuntimeError(f"{key_name} is not configured")
    base_url = llm_base_url()
    if base_url:
        return AsyncOpenAI(api_key=api_key, base_url=base_url)
    return AsyncOpenAI(api_key=api_key)


def _chat_sampling_kwargs() -> dict[str, Any]:
    cfg = _settings()
    kwargs: dict[str, Any] = {"temperature": cfg.llm_temperature}
    if llm_provider() == "minimax":
        kwargs["top_p"] = 0.9
    return kwargs


def sync_chat_json(
    client: OpenAI,
    *,
    messages: list[dict[str, Any]],
    model: str | None = None,
    max_tokens: int = 4096,
) -> str:
    kwargs: dict[str, Any] = {
        "model": model or _settings().llm_model,
        "max_tokens": max_tokens,
        "messages": messages,
        "response_format": {"type": "json_object"},
        **_chat_sampling_kwargs(),
    }
    extra = minimax_extra_body()
    if extra:
        kwargs["extra_body"] = extra
    response = client.chat.completions.create(**kwargs)
    return extract_llm_text(response.choices[0].message.content)


async def async_chat_json(
    client: AsyncOpenAI,
    *,
    messages: list[dict[str, Any]],
    model: str | None = None,
    max_tokens: int = 4096,
) -> str:
    kwargs: dict[str, Any] = {
        "model": model or _settings().llm_model,
        "max_tokens": max_tokens,
        "messages": messages,
        "response_format": {"type": "json_object"},
        **_chat_sampling_kwargs(),
    }
    extra = minimax_extra_body()
    if extra:
        kwargs["extra_body"] = extra
    response = await client.chat.completions.create(**kwargs)
    return extract_llm_text(response.choices[0].message.content)


__all__ = [
    "APIConnectionError",
    "APITimeoutError",
    "AsyncOpenAI",
    "OpenAI",
    "async_chat_json",
    "create_async_client",
    "create_sync_client",
    "extract_llm_text",
    "llm_api_key",
    "llm_configured",
    "llm_provider",
    "minimax_extra_body",
    "parse_llm_json",
    "sync_chat_json",
]