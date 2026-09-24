"""
Tests for the central AIOrchestrator — verifies it correctly coordinates
RAGService, RiskService, LLMService, TranslationService, and
ResponsePrivacyService for both customer and employee modes, without
reimplementing their logic itself.

Uses the same controlled-embedding-mock strategy as test_semantic_rag.py
(see that file's docstring for why: no network access to the real
embedding model in this sandbox) plus mocking of chat_completion for LLM
output, so these tests exercise orchestration/coordination logic
specifically, independent of real model quality.
"""
from unittest.mock import patch

import numpy as np
import pytest

from services.ai_orchestrator import ai_orchestrator
from services.embedding_service import embedding_service
from services.rag_service import _load_and_chunk_knowledge_base, retriever

DIM = 256  # high-dimensional so unrelated random vectors are reliably near-orthogonal (no flaky chance overlap)


def _unit(v):
    return (v / np.linalg.norm(v)).astype("float32")


def _vec(seed):
    return _unit(np.random.default_rng(seed).normal(size=DIM))


@pytest.fixture(autouse=True)
def reset_index():
    retriever._store = None
    yield
    retriever._store = None


@pytest.fixture
def grounded_kb():
    """Installs a fake embedder where every KB chunk and every query used in
    these tests are confidently close together — isolates these tests from
    retrieval-quality concerns (that's test_semantic_rag.py's job) so they
    can focus purely on orchestration."""
    chunks = _load_and_chunk_knowledge_base()
    shared_vec = _vec(1)
    chunk_vectors = {c.text: shared_vec for c in chunks}

    def _fake_embed(texts):
        return np.vstack([chunk_vectors.get(t, shared_vec) for t in texts]).astype("float32")

    with patch.object(embedding_service, "embed", side_effect=_fake_embed):
        yield


# --- Customer Mode ---


def test_customer_mode_returns_sources_and_confidence(grounded_kb):
    with patch("services.ai_orchestrator.chat_completion", return_value="Namaste!\nEN: Hello!"):
        result = ai_orchestrator.handle_customer_query("How do I open an account?", "en", "simple")

    assert result["reply_local"] == "Namaste!"
    assert result["reply_english"] == "Hello!"
    assert result["grounded"] is True
    assert result["confidence"] is not None and result["confidence"] > 0
    assert len(result["sources"]) > 0
    assert all({"topic", "doc_id", "chunk_index", "score"} <= r.keys() for r in result["sources"])


def test_customer_mode_low_risk_by_default(grounded_kb):
    with patch("services.ai_orchestrator.chat_completion", return_value="Reply\nEN: Reply"):
        result = ai_orchestrator.handle_customer_query("What are your working hours?", "en", "simple")

    assert result["risk_level"] == "low"
    assert result["requires_human_review"] is False


def test_customer_mode_flags_high_risk_query_without_blocking_the_reply(grounded_kb):
    # "dispute" is a high-risk term but not an account-data intent, so this
    # isolates risk-flagging behavior from the account-intent path (tested
    # separately in test_account_intents.py).
    with patch("services.ai_orchestrator.chat_completion", return_value="Reply\nEN: Reply"):
        result = ai_orchestrator.handle_customer_query("I want to dispute a transaction on my account", "en", "simple")

    assert result["risk_level"] == "high"
    assert result["requires_human_review"] is True
    # Risk flagging changes framing/metadata, not whether the (grounded)
    # customer-facing reply itself is still returned.
    assert result["reply_local"] == "Reply"


def test_customer_mode_complexity_is_passed_through_to_the_prompt(grounded_kb):
    with patch("services.ai_orchestrator.chat_completion", return_value="Reply\nEN: Reply") as mock_llm:
        ai_orchestrator.handle_customer_query("How do I open an account?", "en", "detailed")

    system_prompt = mock_llm.call_args.args[0]
    assert "precise, complete explanation" in system_prompt  # from COMPLEXITY_INSTRUCTIONS["detailed"]


def test_customer_mode_ungrounded_query_never_calls_the_llm():
    # No grounded_kb fixture here — nothing embeds close together, so
    # retrieval should not be confident and the LLM must be skipped.
    def _fake_embed(texts):
        return np.vstack([_vec(abs(hash(t)) % (2**31)) for t in texts]).astype("float32")

    with patch.object(embedding_service, "embed", side_effect=_fake_embed):
        with patch("services.ai_orchestrator.chat_completion") as mock_llm:
            result = ai_orchestrator.handle_customer_query("What's the weather today?", "en", "simple")
            mock_llm.assert_not_called()

    assert result["grounded"] is False
    assert result["sources"] == []


# --- Employee Mode (Copilot) ---


def test_employee_mode_returns_sources_confidence_and_briefing_fields(grounded_kb):
    fake_json = (
        '{"understood_summary": "Wants to open an account", '
        '"relevant_info": "Needs Aadhaar and PAN", '
        '"suggested_action": "Hand over the account opening form", '
        '"reply_local": "Namaste!", "reply_english": "Hello!"}'
    )
    with patch("services.ai_orchestrator.chat_completion", return_value=fake_json):
        result = ai_orchestrator.handle_employee_query("How do I open an account?", "en", "simple")

    assert result["understood_summary"] == "Wants to open an account"
    assert result["suggested_reply_local"] == "Namaste!"
    assert result["grounded"] is True
    assert len(result["sources"]) > 0
    assert result["confidence"] is not None


def test_employee_mode_prepends_risk_note_to_suggested_action(grounded_kb):
    fake_json = (
        '{"understood_summary": "Wants to dispute a transaction", '
        '"relevant_info": "n/a", '
        '"suggested_action": "Pull up the transaction history", '
        '"reply_local": "Reply", "reply_english": "Reply"}'
    )
    with patch("services.ai_orchestrator.chat_completion", return_value=fake_json):
        result = ai_orchestrator.handle_employee_query("I want to dispute a transaction and report fraud", "en", "simple")

    assert result["risk_level"] == "high"
    assert result["requires_human_review"] is True
    # RiskService's note must actually appear in the suggested action — this
    # is what makes risk analysis observable to the employee, not just an
    # internal flag nobody sees.
    assert "staff member must verify" in result["suggested_action"]
    assert "Pull up the transaction history" in result["suggested_action"]


def test_employee_mode_ungrounded_query_never_calls_the_llm():
    def _fake_embed(texts):
        return np.vstack([_vec(abs(hash(t)) % (2**31)) for t in texts]).astype("float32")

    with patch.object(embedding_service, "embed", side_effect=_fake_embed):
        with patch("services.ai_orchestrator.chat_completion") as mock_llm:
            result = ai_orchestrator.handle_employee_query("Do you sell airline miles credit cards?", "en", "simple")
            mock_llm.assert_not_called()

    assert result["grounded"] is False
    assert result["requires_human_review"] is True


# --- Backward-compatible free functions still work ---


def test_backward_compatible_wrappers_still_work(grounded_kb):
    from services.ai_orchestrator import generate_copilot_briefing, generate_customer_reply

    with patch("services.ai_orchestrator.chat_completion", return_value="Reply\nEN: Reply"):
        chat_result = generate_customer_reply("How do I open an account?", "en", "simple")
    assert chat_result == {"reply_local": "Reply", "reply_english": "Reply"}

    fake_json = (
        '{"understood_summary": "s", "relevant_info": "i", "suggested_action": "a", '
        '"reply_local": "Reply", "reply_english": "Reply"}'
    )
    with patch("services.ai_orchestrator.chat_completion", return_value=fake_json):
        copilot_result = generate_copilot_briefing("How do I open an account?", "en", "simple")
    assert copilot_result["suggested_reply_local"] == "Reply"
