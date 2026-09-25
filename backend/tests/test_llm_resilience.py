"""Groq client reuse, timeouts/retries and the fallback model (services/llm_service.py)."""
from unittest.mock import MagicMock, patch

import pytest

from core.exceptions import UpstreamServiceError
from services import llm_service


def _completion(text="ok"):
    c = MagicMock()
    c.choices = [MagicMock(message=MagicMock(content=text))]
    c.usage = MagicMock(prompt_tokens=10, completion_tokens=5)
    return c


def test_client_is_created_once_with_timeout_and_retries(monkeypatch):
    monkeypatch.setattr(llm_service, "_client", None)
    with patch("groq.Groq") as groq_cls:
        a = llm_service._get_groq_client()
        b = llm_service._get_groq_client()
    assert a is b
    groq_cls.assert_called_once()
    kwargs = groq_cls.call_args.kwargs
    assert kwargs["timeout"] == llm_service.settings.LLM_TIMEOUT_SECONDS
    assert kwargs["max_retries"] == llm_service.settings.LLM_MAX_RETRIES
    monkeypatch.setattr(llm_service, "_client", None)


def test_fallback_model_answers_when_main_model_fails(monkeypatch):
    monkeypatch.setattr(llm_service.settings, "GROQ_CHAT_MODEL", "main-model")
    monkeypatch.setattr(llm_service.settings, "GROQ_FALLBACK_MODEL", "backup-model")
    client = MagicMock()
    client.chat.completions.create.side_effect = [RuntimeError("429 rate limited"), _completion("from backup")]
    with patch.object(llm_service, "_get_groq_client", return_value=client):
        assert llm_service.chat_completion("sys", "hi") == "from backup"
    models = [c.kwargs["model"] for c in client.chat.completions.create.call_args_list]
    assert models == ["main-model", "backup-model"]


def test_error_when_both_models_fail(monkeypatch):
    monkeypatch.setattr(llm_service.settings, "GROQ_CHAT_MODEL", "main-model")
    monkeypatch.setattr(llm_service.settings, "GROQ_FALLBACK_MODEL", "backup-model")
    client = MagicMock()
    client.chat.completions.create.side_effect = RuntimeError("down")
    with patch.object(llm_service, "_get_groq_client", return_value=client):
        with pytest.raises(UpstreamServiceError):
            llm_service.chat_completion("sys", "hi")


def test_no_fallback_call_when_disabled(monkeypatch):
    monkeypatch.setattr(llm_service.settings, "GROQ_CHAT_MODEL", "main-model")
    monkeypatch.setattr(llm_service.settings, "GROQ_FALLBACK_MODEL", "")
    client = MagicMock()
    client.chat.completions.create.side_effect = RuntimeError("down")
    with patch.object(llm_service, "_get_groq_client", return_value=client):
        with pytest.raises(UpstreamServiceError):
            llm_service.chat_completion("sys", "hi")
    assert client.chat.completions.create.call_count == 1


def test_reasoning_setting_only_sent_to_reasoning_models(monkeypatch):
    monkeypatch.setattr(llm_service.settings, "GROQ_CHAT_MODEL", "openai/gpt-oss-120b")
    monkeypatch.setattr(llm_service.settings, "GROQ_FALLBACK_MODEL", "other-model")
    client = MagicMock()
    client.chat.completions.create.side_effect = [RuntimeError("x"), _completion()]
    with patch.object(llm_service, "_get_groq_client", return_value=client):
        llm_service.chat_completion("sys", "hi")
    first, second = client.chat.completions.create.call_args_list
    assert first.kwargs.get("reasoning_effort") == "low"
    assert "reasoning_effort" not in second.kwargs
