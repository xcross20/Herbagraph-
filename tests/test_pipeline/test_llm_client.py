"""MiniMax / OpenAI shared LLM client helpers."""

import pytest

from app.config import get_settings
from app.pipeline.llm_client import (
    DEFAULT_MINIMAX_BASE_URL,
    create_async_client,
    create_sync_client,
    extract_llm_text,
    llm_api_key,
    llm_base_url,
    minimax_extra_body,
    parse_llm_json,
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


def test_missing_key_raises(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "minimax")
    monkeypatch.setenv("MINIMAX_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_settings.cache_clear()

    with pytest.raises(RuntimeError, match="MINIMAX_API_KEY"):
        create_sync_client()
    get_settings.cache_clear()