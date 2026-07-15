"""MiniMax / OpenAI shared LLM client helpers."""

from unittest.mock import Mock

import pytest

from app.config import get_settings
from openai import BadRequestError, RateLimitError

from app.pipeline.llm_client import (
    DEFAULT_MINIMAX_BASE_URL,
    create_async_client,
    create_sync_client,
    extract_llm_text,
    is_llm_fallback_retryable,
    llm_api_key,
    llm_base_url,
    llm_fallback_provider,
    minimax_extra_body,
    parse_llm_json,
    sync_chat_json_with_fallback,
)


def test_extract_llm_text_strips_think_blocks():
    raw = '<think>internal chain</think>\n{"ok": true}'
    assert extract_llm_text(raw) == '{"ok": true}'


def test_extract_llm_text_strips_json_fence():
    raw = '```json\n{"results": []}\n```'
    assert extract_llm_text(raw) == '{"results": []}'


def test_parse_llm_json_after_think_strip():
    assert parse_llm_json('<think>x</think>{"a": 1}') == {"a": 1}


def test_minimax_provider_uses_minimax_key_and_base(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "minimax")
    monkeypatch.setenv("MINIMAX_API_KEY", "mm-test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "oa-should-not-win")
    get_settings.cache_clear()

    assert llm_api_key() == "mm-test-key"
    assert llm_base_url() == DEFAULT_MINIMAX_BASE_URL
    assert minimax_extra_body() == {"reasoning_split": True}

    client = create_sync_client()
    assert client.api_key == "mm-test-key"
    assert client.base_url.host == "api.minimax.io"

    async_client = create_async_client()
    assert async_client.api_key == "mm-test-key"
    get_settings.cache_clear()


def test_openai_provider_uses_default_base(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    get_settings.cache_clear()

    assert llm_api_key() == "sk-test"
    assert llm_base_url() is None
    assert minimax_extra_body() == {}
    get_settings.cache_clear()


def test_is_llm_fallback_retryable_detects_context_and_rate_errors():
    assert is_llm_fallback_retryable(RateLimitError("rate limit", response=Mock(), body=None))
    assert is_llm_fallback_retryable(
        BadRequestError("context_length_exceeded", response=Mock(status_code=400), body=None)
    )
    assert not is_llm_fallback_retryable(RuntimeError("invalid api key"))


def test_auto_fallback_provider_when_openai_primary_and_minimax_key(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("MINIMAX_API_KEY", "mm-test")
    monkeypatch.delenv("LLM_FALLBACK_PROVIDER", raising=False)
    get_settings.cache_clear()
    assert llm_fallback_provider() == "minimax"
    get_settings.cache_clear()


def test_sync_chat_json_with_fallback_retries_minimax(monkeypatch):
    from unittest.mock import Mock

    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("MINIMAX_API_KEY", "mm-test")
    monkeypatch.setenv("LLM_FALLBACK_MODEL", "MiniMax-M2.7")
    get_settings.cache_clear()

    calls: list[tuple[str, str]] = []

    def fake_sync_chat_json(client, *, messages, model=None, max_tokens=4096, provider=None):
        calls.append((provider or "unknown", model or "default"))
        if provider == "openai":
            raise BadRequestError(
                "context_length_exceeded",
                response=Mock(status_code=400),
                body=None,
            )
        return '{"results": []}'

    monkeypatch.setattr("app.pipeline.llm_client.sync_chat_json", fake_sync_chat_json)
    monkeypatch.setattr(
        "app.pipeline.llm_client.create_sync_client_for_provider",
        lambda provider: Mock(provider=provider),
    )

    text, fallback = sync_chat_json_with_fallback(messages=[{"role": "user", "content": "hi"}])
    assert text == '{"results": []}'
    assert fallback == "minimax"
    assert calls[0][0] == "openai"
    assert calls[1] == ("minimax", "MiniMax-M2.7")
    get_settings.cache_clear()


def test_missing_key_raises(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "minimax")
    monkeypatch.setenv("MINIMAX_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_settings.cache_clear()

    with pytest.raises(RuntimeError, match="MINIMAX_API_KEY"):
        create_sync_client()
    get_settings.cache_clear()