"""Unit tests for PatchyLLMClient (patchy_bot/clients/llm.py)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from patchy_bot.clients.llm import PatchyLLMClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client(base_url: str | None = "http://localhost:8000", api_key: str | None = "test-key") -> PatchyLLMClient:
    return PatchyLLMClient(base_url, api_key)


def _fake_response(status_code: int = 200, json_data: dict | None = None, text: str = "") -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    if json_data is not None:
        resp.json.return_value = json_data
    else:
        resp.json.side_effect = ValueError("no JSON")
    return resp


_CHAT_KWARGS: dict[str, Any] = dict(
    messages=[{"role": "user", "content": "hi"}],
    model="primary-model",
    fallback_model="fallback-model",
    max_tokens=100,
    temperature=0.5,
)


# ---------------------------------------------------------------------------
# ready()
# ---------------------------------------------------------------------------


def test_llm_ready_returns_true_when_configured() -> None:
    client = _make_client("http://localhost:8000", "sk-test")
    assert client.ready() is True


def test_llm_ready_returns_false_when_missing_base_url() -> None:
    client = _make_client(base_url=None, api_key="sk-test")
    assert client.ready() is False


def test_llm_ready_returns_false_when_missing_api_key() -> None:
    client = _make_client(base_url="http://localhost:8000", api_key=None)
    assert client.ready() is False


# ---------------------------------------------------------------------------
# _extract_content()
# ---------------------------------------------------------------------------


def test_extract_content_string() -> None:
    data = {"choices": [{"message": {"content": "hello"}}]}
    assert PatchyLLMClient._extract_content(data) == "hello"


def test_extract_content_array() -> None:
    data = {"choices": [{"message": {"content": [{"text": "part1"}, {"text": "part2"}]}}]}
    assert PatchyLLMClient._extract_content(data) == "part1\npart2"


def test_extract_content_empty_choices() -> None:
    assert PatchyLLMClient._extract_content({"choices": []}) == ""


def test_extract_content_no_choices_key() -> None:
    assert PatchyLLMClient._extract_content({}) == ""


# ---------------------------------------------------------------------------
# chat()
# ---------------------------------------------------------------------------


def test_chat_returns_content_and_model_on_success(monkeypatch) -> None:
    client = _make_client()
    fake_resp = _fake_response(200, {"choices": [{"message": {"content": "Hello!"}}]})
    monkeypatch.setattr(client.session, "post", MagicMock(return_value=fake_resp))

    content, model_id = client.chat(**_CHAT_KWARGS)
    assert content == "Hello!"
    assert model_id == "primary-model"


def test_chat_falls_back_on_404(monkeypatch) -> None:
    client = _make_client()

    fail_resp = _fake_response(404, text="model not supported")
    ok_resp = _fake_response(200, {"choices": [{"message": {"content": "fallback ok"}}]})

    mock_post = MagicMock(side_effect=[fail_resp, ok_resp])
    monkeypatch.setattr(client.session, "post", mock_post)

    content, model_id = client.chat(**_CHAT_KWARGS)
    assert content == "fallback ok"
    assert model_id == "fallback-model"
    assert "primary-model" in client._unsupported_models


def test_chat_unsupported_model_not_retried(monkeypatch) -> None:
    client = _make_client()
    # Pre-mark primary as unsupported
    client._unsupported_models.add("primary-model")

    ok_resp = _fake_response(200, {"choices": [{"message": {"content": "only fallback"}}]})
    mock_post = MagicMock(return_value=ok_resp)
    monkeypatch.setattr(client.session, "post", mock_post)

    content, model_id = client.chat(**_CHAT_KWARGS)
    assert content == "only fallback"
    assert model_id == "fallback-model"
    # session.post should have been called exactly once (skipped primary)
    assert mock_post.call_count == 1


def test_chat_empty_response_triggers_fallback(monkeypatch) -> None:
    client = _make_client()

    empty_resp = _fake_response(200, {"choices": [{"message": {"content": ""}}]})
    ok_resp = _fake_response(200, {"choices": [{"message": {"content": "got it"}}]})

    mock_post = MagicMock(side_effect=[empty_resp, ok_resp])
    monkeypatch.setattr(client.session, "post", mock_post)

    content, model_id = client.chat(**_CHAT_KWARGS)
    assert content == "got it"
    assert model_id == "fallback-model"


def test_chat_raises_when_all_models_fail(monkeypatch) -> None:
    client = _make_client()

    fail_resp = _fake_response(500, text="internal server error")
    mock_post = MagicMock(return_value=fail_resp)
    monkeypatch.setattr(client.session, "post", mock_post)

    with pytest.raises(RuntimeError, match="HTTP 500"):
        client.chat(**_CHAT_KWARGS)
