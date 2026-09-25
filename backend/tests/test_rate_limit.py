"""Rate limiting (services/rate_limit.py)."""
from unittest.mock import patch

import pytest

from auth.security import create_access_token
from services.rate_limit import SlidingWindowLimiter, limiter, settings


@pytest.fixture
def limits_on(monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    limiter.reset()
    yield
    limiter.reset()


def _fake_answer(*a, **k):
    return {"reply_local": "x", "reply_english": "x", "spoken_response": "x", "sources": [], "confidence": 0.9, "grounded": True}


def test_sliding_window_allows_up_to_limit_then_blocks():
    lim = SlidingWindowLimiter()
    assert all(lim.hit("k", 3)[0] for _ in range(3))
    allowed, retry_after = lim.hit("k", 3)
    assert not allowed and 1 <= retry_after <= 61
    assert lim.hit("other", 3)[0]  # keys are independent


def test_window_expires():
    lim = SlidingWindowLimiter()
    with patch("services.rate_limit.time.monotonic", side_effect=[0.0, 0.0, 61.0]):
        assert lim.hit("k", 2)[0] and lim.hit("k", 2)[0]
        assert lim.hit("k", 2)[0]  # first two are older than 60 s


def test_customer_chat_limited_per_session_not_per_branch(client, limits_on, monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_CUSTOMER_AI_PER_MIN", 3)
    a = client.post("/api/customer/session/start", json={"language": "mr"}).json()
    b = client.post("/api/customer/session/start", json={"language": "mr"}).json()

    def ask(s):
        return client.post("/api/customer/chat", headers={"Authorization": f"Bearer {s['customer_token']}"},
                           json={"session_id": s["session_id"], "text": "bank hours", "language": "mr"})

    with patch("api.customer.ai_orchestrator.handle_customer_query", side_effect=_fake_answer):
        assert [ask(a).status_code for _ in range(3)] == [200, 200, 200]
        blocked = ask(a)
        assert blocked.status_code == 429 and int(blocked.headers["Retry-After"]) >= 1
        # Another customer at the same kiosk (same IP) is not affected.
        assert ask(b).status_code == 200


def test_ip_ceiling_applies_across_sessions(client, limits_on, monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_IP_AI_PER_MIN", 2)
    sessions = [client.post("/api/customer/session/start", json={"language": "hi"}).json() for _ in range(3)]
    with patch("api.customer.ai_orchestrator.handle_customer_query", side_effect=_fake_answer):
        codes = [client.post("/api/customer/chat", headers={"Authorization": f"Bearer {s['customer_token']}"},
                             json={"session_id": s["session_id"], "text": "x", "language": "hi"}).status_code for s in sessions]
    assert codes == [200, 200, 429]


def test_login_attempts_are_limited_per_username(client, limits_on, monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_LOGIN_PER_USER_PER_MIN", 3)
    codes = [client.post("/api/auth/login", data={"username": "staff", "password": "wrong"}).status_code for _ in range(4)]
    assert codes == [401, 401, 401, 429]


def test_session_start_limited_per_ip(client, limits_on, monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_SESSION_START_PER_MIN", 2)
    codes = [client.post("/api/customer/session/start", json={"language": "mr"}).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


def test_staff_ai_limited_per_staff_member(client, limits_on, monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_STAFF_AI_PER_MIN", 1)
    fake = {"understood_summary": "s", "relevant_info": "i", "suggested_action": "a", "suggested_reply_local": "r",
            "suggested_reply_english": "r", "spoken_response": "r", "sources": [], "grounded": True}
    h1 = {"Authorization": f"Bearer {create_access_token('teller1')}"}
    h2 = {"Authorization": f"Bearer {create_access_token('teller2')}"}
    with patch("api.copilot.ai_orchestrator.handle_employee_query", return_value=fake):
        assert client.post("/api/copilot", headers=h1, json={"query": "q"}).status_code == 200
        assert client.post("/api/copilot", headers=h1, json={"query": "q"}).status_code == 429
        assert client.post("/api/copilot", headers=h2, json={"query": "q"}).status_code == 200


def test_disabled_by_setting(client, monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", False)
    monkeypatch.setattr(settings, "RATE_LIMIT_SESSION_START_PER_MIN", 1)
    codes = [client.post("/api/customer/session/start", json={"language": "mr"}).status_code for _ in range(3)]
    assert codes == [200, 200, 200]
