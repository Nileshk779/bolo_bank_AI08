"""
Tests for the structured session summary (services/session_service.py).

Mocks chat_completion since the real Groq API isn't reachable in this
sandbox (see other test files' docstrings for the same constraint) — these
tests verify the orchestration around the LLM call: prompt construction,
JSON parsing, defense-in-depth redaction of any sensitive value that slips
into the summary, and the empty-session case. They don't validate the real
model's summarization quality.
"""
import json
from unittest.mock import patch

from services.session_service import generate_structured_summary


def _turns():
    return [
        {"role": "customer", "language": "mr", "text_local": "माझी पेन्शन आली नाही", "text_english": "My pension has not arrived"},
        {
            "role": "assistant",
            "language": "mr",
            "text_local": "मे मध्ये शेवटचा हप्ता मिळाला होता का?",
            "text_english": "Did you receive your last installment in May?",
        },
        {"role": "customer", "language": "mr", "text_local": "हो, मे मध्ये मिळाला होता", "text_english": "Yes, I received it in May"},
    ]


def test_structured_summary_matches_expected_shape():
    fake_json = json.dumps(
        {
            "customer_issue": "Pension payment not received.",
            "important_information": ["Last payment received in May.", "Customer has passbook."],
            "relevant_policy": "Pension credit status must be verified.",
            "recommended_next_action": "Verify pension transaction status.",
            "unresolved": "Account verification required.",
        }
    )
    with patch("services.session_service.chat_completion", return_value=fake_json) as mock_llm:
        summary = generate_structured_summary(_turns(), "mr")

    assert summary["language"] == "Marathi"
    assert summary["customer_issue"] == "Pension payment not received."
    assert summary["important_information"] == ["Last payment received in May.", "Customer has passbook."]
    assert summary["relevant_policy"] == "Pension credit status must be verified."
    assert summary["recommended_next_action"] == "Verify pension transaction status."
    assert summary["unresolved"] == "Account verification required."

    # The transcript was actually passed to the LLM, not fabricated.
    system_prompt = mock_llm.call_args.args[0]
    assert "माझी पेन्शन आली नाही" in system_prompt


def test_empty_session_returns_placeholder_without_calling_the_llm():
    with patch("services.session_service.chat_completion") as mock_llm:
        summary = generate_structured_summary([], "en")
        mock_llm.assert_not_called()

    assert summary["customer_issue"] == "No interaction recorded in this session."
    assert summary["important_information"] == []


def test_malformed_llm_json_falls_back_to_empty_fields_not_a_crash():
    with patch("services.session_service.chat_completion", return_value="not valid json {{{"):
        summary = generate_structured_summary(_turns(), "en")

    assert summary["customer_issue"] == ""
    assert summary["important_information"] == []


def test_sensitive_value_leaking_into_transcript_is_redacted_from_summary():
    """A customer might say their real account number out loud during the
    conversation (logged verbatim in the turn) — the summary must not
    repeat it even if the LLM echoes it back despite the prompt instruction."""
    fake_json = json.dumps(
        {
            "customer_issue": "Customer wants to verify their account.",
            "important_information": ["Customer's account number is 1234567890123."],
            "relevant_policy": "",
            "recommended_next_action": "Verify identity.",
            "unresolved": "",
        }
    )
    with patch("services.session_service.chat_completion", return_value=fake_json):
        summary = generate_structured_summary(_turns(), "en")

    assert "1234567890123" not in summary["important_information"][0]
    assert "[sensitive information omitted]" in summary["important_information"][0]
