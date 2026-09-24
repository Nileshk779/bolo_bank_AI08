"""
Automatic explanation level (services/clarification_service.py) and its use
in customer chat, staff chat and the Copilot.
"""
from unittest.mock import patch

import pytest

from auth.security import create_access_token
from services.clarification_service import detect_feedback, next_level, plan

STAFF = {"Authorization": f"Bearer {create_access_token('staff')}"}


@pytest.mark.parametrize(
    "text",
    [
        "I don't understand", "didn't get it", "this is too complicated", "please explain again", "samajh nahi aaya",
        "मुझे समझ नहीं आया", "आसान भाषा में बताइए", "मला समजले नाही", "सोप्या भाषेत सांगा",
        "ನನಗೆ ಅರ್ಥವಾಗಲಿಲ್ಲ", "నాకు అర్థం కాలేదు",
    ],
)
def test_detects_did_not_understand_in_all_languages(text):
    assert detect_feedback(text) == "simpler"


@pytest.mark.parametrize(
    "text",
    ["tell me more", "explain in detail", "aur batao", "विस्तार से बताइए", "सविस्तर सांगा", "ವಿವರವಾಗಿ ಹೇಳಿ", "వివరంగా చెప్పండి"],
)
def test_detects_tell_me_more_in_all_languages(text):
    assert detect_feedback(text) == "more_detail"


@pytest.mark.parametrize("text", ["How do I open an account?", "मेरा पासबुक खो गया", "हो", "नाही", "What is the minimum balance?"])
def test_ordinary_questions_are_not_feedback(text):
    assert detect_feedback(text) is None


def test_level_moves_in_the_right_direction():
    assert next_level("detailed", "simpler") == ("normal", "simpler")
    assert next_level("normal", "simpler") == ("simple", "simpler")
    assert next_level("simple", "simpler") == ("simple", "reexplain")  # can't go lower: re-explain with an example
    assert next_level("simple", "more_detail") == ("normal", "more_detail")
    assert next_level("normal", "more_detail") == ("detailed", "more_detail")
    assert next_level("detailed", "more_detail") == ("detailed", "more_detail")


def test_short_feedback_re_answers_the_previous_question():
    p = plan("मला समजले नाही", "normal", previous_question="एफडी म्हणजे काय?")
    assert p.query == "एफडी म्हणजे काय?"
    assert p.complexity == "simple" and p.level_change == "simpler"
    assert p.reexplained_question == "एफडी म्हणजे काय?"
    assert p.instruction


def test_feedback_with_a_new_question_answers_the_new_question():
    text = "I don't understand these terms, can you tell me what the minimum balance for a savings account is"
    p = plan(text, "detailed", previous_question="What is an FD?")
    assert p.query == text and p.complexity == "normal" and p.reexplained_question is None


def test_no_feedback_keeps_level():
    p = plan("How do I close my account?", "normal", previous_question="anything")
    assert (p.query, p.complexity, p.level_change, p.instruction) == ("How do I close my account?", "normal", None, None)


# ------------------------------------------------------------------ API --- #
def _fake_customer_query(text, language, complexity, followup=None):
    return {
        "reply_local": f"answer to [{text}] at {complexity}", "reply_english": "x", "spoken_response": "x",
        "sources": [], "confidence": 0.9, "grounded": True, "_followup": followup,
    }


def test_customer_portal_re_explains_previous_question_more_simply(client):
    s = client.post("/api/customer/session/start", json={"language": "mr"}).json()
    headers = {"Authorization": f"Bearer {s['customer_token']}"}
    body = {"session_id": s["session_id"], "language": "mr"}

    with patch("api.customer.ai_orchestrator.handle_customer_query", side_effect=_fake_customer_query) as orch:
        first = client.post("/api/customer/chat", headers=headers, json={**body, "text": "एफडी म्हणजे काय?", "complexity": "normal"}).json()
        assert first["complexity_used"] == "normal" and first["level_change"] is None

        again = client.post("/api/customer/chat", headers=headers, json={**body, "text": "मला समजले नाही", "complexity": "normal"}).json()
        assert again["complexity_used"] == "simple"
        assert again["level_change"] == "simpler"
        assert again["reexplained_question"] == "एफडी म्हणजे काय?"
        assert orch.call_args.kwargs["text"] == "एफडी म्हणजे काय?"
        assert orch.call_args.kwargs["followup"]

        still = client.post("/api/customer/chat", headers=headers, json={**body, "text": "अजूनही समजले नाही", "complexity": "simple"}).json()
        assert still["level_change"] == "reexplain" and still["reexplained_question"] == "एफडी म्हणजे काय?"

        more = client.post("/api/customer/chat", headers=headers, json={**body, "text": "सविस्तर सांगा", "complexity": "simple"}).json()
        assert more["complexity_used"] == "normal" and more["level_change"] == "more_detail"


def test_staff_chat_uses_the_same_logic(client):
    sid = "clarify-staff-1"
    with patch("api.chat.ai_orchestrator.handle_customer_query", side_effect=_fake_customer_query):
        client.post("/api/chat", headers=STAFF, json={"session_id": sid, "text": "What is a recurring deposit?", "language": "hi", "complexity": "simple"})
        r = client.post("/api/chat", headers=STAFF, json={"session_id": sid, "text": "tell me more", "language": "hi", "complexity": "simple"}).json()
    assert r["complexity_used"] == "normal" and r["reexplained_question"] == "What is a recurring deposit?"


def test_copilot_uses_previous_query(client):
    fake = {
        "understood_summary": "s", "relevant_info": "i", "suggested_action": "a", "suggested_reply_local": "r",
        "suggested_reply_english": "r", "spoken_response": "r", "sources": [], "grounded": True,
    }
    with patch("api.copilot.ai_orchestrator.handle_employee_query", return_value=fake) as orch:
        r = client.post(
            "/api/copilot", headers=STAFF,
            json={"query": "customer says she didn't understand", "previous_query": "Explain Form 15H", "language": "hi", "complexity": "detailed"},
        ).json()
    assert orch.call_args.kwargs["query"] == "Explain Form 15H"
    assert orch.call_args.kwargs["complexity"] == "normal"
    assert r["level_change"] == "simpler"
