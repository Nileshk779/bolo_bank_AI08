"""
Tests for Privacy-Aware Voice Disclosure.

Covers the exact scenarios from the feature spec:
  "What is my balance?"
  "What was my last transaction?"
  "Tell me my account number."
  "What is my OTP?"
  "What documents do I need?"
across languages, plus the underlying account_service intent detection and
response_privacy_service regex-based defense-in-depth layer directly.
"""
import tempfile
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from services import account_service, response_privacy_service
from services.ai_orchestrator import ai_orchestrator
from services.embedding_service import embedding_service
from services.rag_service import _load_and_chunk_knowledge_base, retriever

DIM = 256


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
    """Every KB chunk and query embeds close together — isolates these
    tests from retrieval-quality concerns (covered in test_semantic_rag.py)
    so they can focus on the privacy/account-intent behavior."""
    chunks = _load_and_chunk_knowledge_base()
    shared_vec = _vec(1)
    chunk_vectors = {c.text: shared_vec for c in chunks}

    def _fake_embed(texts):
        return np.vstack([chunk_vectors.get(t, shared_vec) for t in texts]).astype("float32")

    with patch.object(embedding_service, "embed", side_effect=_fake_embed):
        yield


LANGUAGES = ["en", "hi", "mr", "te", "kn"]


# --- 1. "What is my balance?" ------------------------------------------- #


@pytest.mark.parametrize("language", LANGUAGES)
def test_balance_question_never_speaks_the_amount_shows_it_on_screen(grounded_kb, language):
    with patch("services.ai_orchestrator.chat_completion") as mock_llm:
        result = ai_orchestrator.handle_customer_query("What is my current balance?", language, "simple")
        mock_llm.assert_not_called()  # no real balance data for an LLM to be grounded in — never even tries

    assert result["sensitive"] is True
    assert "12450" not in result["spoken_response"]
    assert "₹" not in result["spoken_response"]
    assert result["visual_data"]["type"] == "balance"
    assert result["visual_data"]["value"] == "12450"  # the real (demo) value — screen only
    assert result["reply_local"] == result["spoken_response"]  # prose never carries the raw value either


def test_balance_response_structure_matches_spec_shape(grounded_kb):
    with patch("services.ai_orchestrator.chat_completion"):
        result = ai_orchestrator.handle_customer_query("What's my balance?", "en", "simple")

    # Matches the required {spoken_response, visual_data, sensitive} shape.
    assert set(["spoken_response", "visual_data", "sensitive"]) <= result.keys()
    assert result["visual_data"]["currency"] == "INR"


# --- 2. "What was my last transaction?" ---------------------------------- #


def test_last_transaction_question_shows_details_on_screen_only(grounded_kb):
    with patch("services.ai_orchestrator.chat_completion") as mock_llm:
        result = ai_orchestrator.handle_customer_query("What was my last transaction?", "en", "simple")
        mock_llm.assert_not_called()

    assert result["sensitive"] is True
    assert result["visual_data"]["type"] == "transaction"
    assert "850" not in result["spoken_response"]
    assert result["visual_data"]["value"]["amount"] == "850"


# --- 3. "Tell me my account number." ------------------------------------- #


def test_account_number_question_never_spoken(grounded_kb):
    with patch("services.ai_orchestrator.chat_completion") as mock_llm:
        result = ai_orchestrator.handle_customer_query("Tell me my account number.", "en", "simple")
        mock_llm.assert_not_called()

    assert result["sensitive"] is True
    assert "1234567890123" not in result["spoken_response"]
    assert result["visual_data"]["type"] == "account_number"
    assert result["visual_data"]["value"].endswith("0123")
    assert "1234567890123" not in result["visual_data"]["value"]


# --- 4. "What is my OTP?" (and PIN/CVV/Aadhaar — never disclosed at all) - #


@pytest.mark.parametrize(
    "question,expected_intent",
    [
        ("What is my OTP?", "otp"),
        ("Can you tell me my ATM PIN?", "pin"),
        ("What's the CVV on my card?", "cvv"),
        ("What is my Aadhaar number?", "id_number"),
    ],
)
def test_otp_pin_cvv_aadhaar_are_never_disclosed_spoken_or_shown(grounded_kb, question, expected_intent):
    with patch("services.ai_orchestrator.chat_completion") as mock_llm:
        result = ai_orchestrator.handle_customer_query(question, "en", "simple")
        mock_llm.assert_not_called()

    assert result["sensitive"] is True
    assert result["visual_data"] is None  # nothing to show — not just nothing spoken
    assert result["risk_level"] == "high"
    assert result["requires_human_review"] is True
    assert account_service.detect_account_intent(question) == expected_intent


# --- 5. "What documents do I need?" (non-sensitive -> normal voice+screen) #


def test_non_sensitive_policy_question_is_spoken_normally(grounded_kb):
    with patch("services.ai_orchestrator.chat_completion", return_value="Aadhaar aur PAN chahiye.\nEN: You need Aadhaar and PAN."):
        result = ai_orchestrator.handle_customer_query("What documents do I need to open a savings account?", "en", "simple")

    assert result["sensitive"] is False
    assert result["visual_data"] is None
    assert result["spoken_response"] == result["reply_local"] == "Aadhaar aur PAN chahiye."


# --- Employee Copilot mode gets the same protection ---------------------- #


def test_copilot_also_never_speaks_balance(grounded_kb):
    with patch("services.ai_orchestrator.chat_completion") as mock_llm:
        result = ai_orchestrator.handle_employee_query("What is the customer's balance?", "en", "simple")
        mock_llm.assert_not_called()

    assert result["sensitive"] is True
    assert "12450" not in result["spoken_response"]
    assert result["visual_data"]["type"] == "balance"
    assert "do not read the sensitive value aloud" in result["suggested_action"].lower()


# --- Defense-in-depth: regex layer over free-form LLM prose -------------- #


def test_defense_in_depth_redacts_leaked_balance_in_llm_prose(grounded_kb):
    # Simulates the LLM somehow producing personal financial data in its
    # answer despite being grounded only in policy documents — the regex
    # safety net must still catch it before it reaches spoken_response.
    with patch(
        "services.ai_orchestrator.chat_completion",
        return_value="Your current balance is Rs. 42,350 today.\nEN: Your current balance is Rs. 42,350 today.",
    ):
        result = ai_orchestrator.handle_customer_query("Tell me something about savings accounts", "en", "simple")

    assert result["sensitive"] is True
    assert "42,350" not in result["spoken_response"]
    # But the full text is still preserved for on-screen/staff-transcript display.
    assert "42,350" in result["reply_local"]


def test_defense_in_depth_does_not_redact_generic_policy_figures():
    result = response_privacy_service.protect_for_speech(
        "The minimum balance requirement is Rs. 1,000 for urban branches.", language="en"
    )
    assert result.redacted is False
    assert "1,000" in result.safe_text


# --- /api/speak enforces this unconditionally (no bypass) ---------------- #


def _disposable_mp3() -> Path:
    """A throwaway file safe for a mocked /api/speak response to actually
    delete via its background cleanup task — NEVER a real source file (a
    previous version of this test used __file__ directly and the test file
    was deleted by the very cleanup behavior it was meant to exercise)."""
    f = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    f.write(b"fake-mp3-bytes")
    f.close()
    return Path(f.name)


def test_speak_endpoint_always_filters_regardless_of_caller(client):
    """Even if a caller passes raw sensitive-looking text directly to
    /api/speak (bypassing the orchestrator entirely), the endpoint itself
    must still strip it — this is the "no bypass flag" guarantee."""
    with patch("api.voice.synthesize_speech") as mock_synth:
        mock_synth.return_value = _disposable_mp3()
        token = _login(client)
        client.post(
            "/api/speak",
            data={"text": "Your current balance is Rs. 99,999.", "language": "en"},
            headers={"Authorization": f"Bearer {token}"},
        )
        spoken_text_sent_to_tts = mock_synth.call_args.args[0]
        assert "99,999" not in spoken_text_sent_to_tts


def _login(client) -> str:
    res = client.post("/api/auth/login", data={"username": "staff", "password": "bolobank123"})
    return res.json()["access_token"]
