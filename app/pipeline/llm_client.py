"""Shared LLM client factory — OpenAI or MiniMax (OpenAI-compatible API)."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    BadRequestError,
    OpenAI,
    RateLimitError,
)

from app.config import get_settings

logger = logging.getLogger(__name__)

_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)

DEFAULT_MINIMAX_BASE_URL = "https://api.minimax.io/v1"
DEFAULT_MINIMAX_FALLBACK_MODEL = "MiniMax-M2.7"

_RETRYABLE_ERROR_MARKERS = (
    "context_length_exceeded",
    "maximum context length",
    "context window",
    "max_tokens",
    "max tokens",
    "token limit",
    "too many tokens",
    "rate_limit",
    "rate limit",
    "too many requests",
    "request too large",
    "payload too large",
    "insufficient_quota",
)


def _settings():
    return get_settings()


def llm_provider() -> str:
    return (_settings().llm_provider or "openai").strip().lower()


def llm_fallback_provider() -> str | None:
    """Secondary provider when the primary hits context/token/rate limits."""
    cfg = _settings()
    explicit = (cfg.llm_fallback_provider or "").strip().lower()
    if explicit:
        return explicit
    primary = llm_provider()
    if primary == "openai" and cfg.minimax_api_key:
        return "minimax"
    if primary == "minimax" and cfg.openai_api_key:
        return "openai"
    return None


def llm_fallback_model(provider: str | None = None) -> str:
    cfg = _settings()
    if cfg.llm_fallback_model:
        return cfg.llm_fallback_model
    resolved = (provider or llm_fallback_provider() or "").strip().lower()
    if resolved == "minimax":
        return DEFAULT_MINIMAX_FALLBACK_MODEL
    return cfg.llm_model


def _provider_api_key(provider: str) -> str:
    cfg = _settings()
    if provider == "minimax":
        return cfg.minimax_api_key or cfg.openai_api_key
    return cfg.openai_api_key


def llm_api_key() -> str:
    return _provider_api_key(llm_provider())


def _provider_base_url(provider: str) -> str | None:
    cfg = _settings()
    if cfg.llm_base_url:
        return cfg.llm_base_url
    if provider == "minimax":
        return DEFAULT_MINIMAX_BASE_URL
    return None


def llm_base_url() -> str | None:
    return _provider_base_url(llm_provider())


def llm_configured() -> bool:
    return bool(llm_api_key())


def llm_fallback_configured() -> bool:
    fb = llm_fallback_provider()
    return bool(fb and _provider_api_key(fb))


def _minimax_extra_body(provider: str) -> dict[str, Any]:
    """Separate M2.x thinking traces from the answer payload when supported."""
    if provider == "minimax":
        return {"reasoning_split": True}
    return {}


def minimax_extra_body() -> dict[str, Any]:
    return _minimax_extra_body(llm_provider())


def is_llm_fallback_retryable(exc: Exception) -> bool:
    """True when a secondary provider may succeed (context/token/rate limits)."""
    if isinstance(exc, RateLimitError):
        return True
    if isinstance(exc, APIStatusError) and exc.status_code in (413, 429):
        return True
    if isinstance(exc, BadRequestError):
        msg = str(exc).lower()
        return any(marker in msg for marker in _RETRYABLE_ERROR_MARKERS)
    msg = str(exc).lower()
    return any(marker in msg for marker in _RETRYABLE_ERROR_MARKERS)


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


def create_sync_client_for_provider(provider: str) -> OpenAI:
    api_key = _provider_api_key(provider)
    if not api_key:
        key_name = "MINIMAX_API_KEY" if provider == "minimax" else "OPENAI_API_KEY"
        raise RuntimeError(f"{key_name} is not configured")
    base_url = _provider_base_url(provider)
    if base_url:
        return OpenAI(api_key=api_key, base_url=base_url)
    return OpenAI(api_key=api_key)


def create_async_client_for_provider(provider: str) -> AsyncOpenAI:
    api_key = _provider_api_key(provider)
    if not api_key:
        key_name = "MINIMAX_API_KEY" if provider == "minimax" else "OPENAI_API_KEY"
        raise RuntimeError(f"{key_name} is not configured")
    base_url = _provider_base_url(provider)
    if base_url:
        return AsyncOpenAI(api_key=api_key, base_url=base_url)
    return AsyncOpenAI(api_key=api_key)


def create_sync_client() -> OpenAI:
    return create_sync_client_for_provider(llm_provider())


def create_async_client() -> AsyncOpenAI:
    return create_async_client_for_provider(llm_provider())


def _chat_sampling_kwargs(provider: str) -> dict[str, Any]:
    cfg = _settings()
    kwargs: dict[str, Any] = {"temperature": cfg.llm_temperature}
    if provider == "minimax":
        kwargs["top_p"] = 0.9
    return kwargs


def sync_chat_json(
    client: OpenAI,
    *,
    messages: list[dict[str, Any]],
    model: str | None = None,
    max_tokens: int = 4096,
    provider: str | None = None,
) -> str:
    resolved_provider = provider or llm_provider()
    kwargs: dict[str, Any] = {
        "model": model or _settings().llm_model,
        "max_tokens": max_tokens,
        "messages": messages,
        "response_format": {"type": "json_object"},
        **_chat_sampling_kwargs(resolved_provider),
    }
    extra = _minimax_extra_body(resolved_provider)
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
    provider: str | None = None,
) -> str:
    resolved_provider = provider or llm_provider()
    kwargs: dict[str, Any] = {
        "model": model or _settings().llm_model,
        "max_tokens": max_tokens,
        "messages": messages,
        "response_format": {"type": "json_object"},
        **_chat_sampling_kwargs(resolved_provider),
    }
    extra = _minimax_extra_body(resolved_provider)
    if extra:
        kwargs["extra_body"] = extra
    response = await client.chat.completions.create(**kwargs)
    return extract_llm_text(response.choices[0].message.content)


def sync_chat_json_with_fallback(
    *,
    messages: list[dict[str, Any]],
    model: str | None = None,
    max_tokens: int = 4096,
) -> tuple[str, str | None]:
    """Call primary LLM; on token/context/rate errors retry with fallback provider."""
    primary = llm_provider()
    client = create_sync_client_for_provider(primary)
    try:
        return sync_chat_json(
            client,
            messages=messages,
            model=model,
            max_tokens=max_tokens,
            provider=primary,
        ), None
    except Exception as exc:
        if not is_llm_fallback_retryable(exc):
            raise
        fallback = llm_fallback_provider()
        if not fallback or fallback == primary or not _provider_api_key(fallback):
            raise
        logger.warning(
            "Primary LLM provider %s failed (%s); falling back to %s",
            primary,
            exc,
            fallback,
        )
        fb_client = create_sync_client_for_provider(fallback)
        text = sync_chat_json(
            fb_client,
            messages=messages,
            model=llm_fallback_model(fallback),
            max_tokens=max_tokens,
            provider=fallback,
        )
        return text, fallback


async def async_chat_json_with_fallback(
    *,
    messages: list[dict[str, Any]],
    model: str | None = None,
    max_tokens: int = 4096,
    client: AsyncOpenAI | None = None,
) -> tuple[str, str | None]:
    """Async variant: primary provider then optional fallback on retryable errors."""
    primary = llm_provider()
    owns_client = client is None
    client = client or create_async_client_for_provider(primary)
    try:
        try:
            return (
                await async_chat_json(
                    client,
                    messages=messages,
                    model=model,
                    max_tokens=max_tokens,
                    provider=primary,
                ),
                None,
            )
        except Exception as exc:
            if not is_llm_fallback_retryable(exc):
                raise
            fallback = llm_fallback_provider()
            if not fallback or fallback == primary or not _provider_api_key(fallback):
                raise
            logger.warning(
                "Primary LLM provider %s failed (%s); falling back to %s",
                primary,
                exc,
                fallback,
            )
            if owns_client and hasattr(client, "close"):
                await client.close()
                owns_client = False
            fb_client = create_async_client_for_provider(fallback)
            text = await async_chat_json(
                fb_client,
                messages=messages,
                model=llm_fallback_model(fallback),
                max_tokens=max_tokens,
                provider=fallback,
            )
            if hasattr(fb_client, "close"):
                await fb_client.close()
            return text, fallback
    finally:
        if owns_client and hasattr(client, "close"):
            await client.close()


__all__ = [
    "APIConnectionError",
    "APITimeoutError",
    "AsyncOpenAI",
    "OpenAI",
    "async_chat_json",
    "async_chat_json_with_fallback",
    "create_async_client",
    "create_async_client_for_provider",
    "create_sync_client",
    "create_sync_client_for_provider",
    "extract_llm_text",
    "is_llm_fallback_retryable",
    "llm_api_key",
    "llm_configured",
    "llm_fallback_configured",
    "llm_fallback_model",
    "llm_fallback_provider",
    "llm_provider",
    "minimax_extra_body",
    "parse_llm_json",
    "sync_chat_json",
    "sync_chat_json_with_fallback",
]