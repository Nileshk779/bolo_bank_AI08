"""
Branch manager dashboard (services/analytics_service.py, /api/dashboard).
"""
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from auth.security import create_access_token
from database.models import InteractionEvent
from database.session import SessionLocal
from services import analytics_service as analytics
from services import llm_service

STAFF = {"Authorization": f"Bearer {create_access_token('staff')}"}


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.close()


def _answer(**kw):
    base = {"reply_local": "x", "reply_english": "x", "spoken_response": "x", "sources": [], "confidence": None,
            "grounded": True, "requires_human_review": False, "sensitive": False}
    return {**base, **kw}


def test_usage_tracking_counts_tokens_per_request():
    class Usage:
        prompt_tokens, completion_tokens = 1200, 300

    class Completion:
        usage = Usage()
        choices = [type("C", (), {"message": type("M", (), {"content": "ok"})()})()]

    with patch.object(llm_service, "_get_groq_client") as client:
        client.return_value.chat.completions.create.return_value = Completion()
        llm_service.start_usage_tracking()
        llm_service.chat_completion("sys", "hi")
        llm_service.chat_completion("sys", "hi again")
    assert llm_service.tracked_usage() == {"llm_calls": 2, "prompt_tokens": 2400, "completion_tokens": 600}


def test_record_answer_classifies_answered_unanswered_and_account_queries(db):
    sid = "dash-t1"
    llm_service.start_usage_tracking()
    analytics.record_answer(db, channel="customer_portal", session_id=sid, language="mr", question="passbook harvle",
                            result=_answer(sources=[{"topic": "Lost Passbook", "doc_id": "KB019", "chunk_index": 0, "score": 0.7}], confidence=0.7))
    analytics.record_answer(db, channel="customer_portal", session_id=sid, language="mr",
                            question="my account 123456789012 sukanya scheme?", result=_answer(grounded=False, confidence=0.2))
    analytics.record_answer(db, channel="customer_portal", session_id=sid, language="mr", question="balance?",
                            result=_answer(grounded=False, sensitive=True))
    rows = db.query(InteractionEvent).filter_by(session_id=sid).order_by(InteractionEvent.id).all()
    assert (rows[0].answered_by_ai, rows[0].topic, rows[0].unanswered_text) == (1, "Lost Passbook", None)
    assert rows[1].handed_to_staff == 1 and "sukanya" in rows[1].unanswered_text
    assert "123456789012" not in rows[1].unanswered_text  # sensitive values redacted
    assert rows[2].account_query == 1 and rows[2].answered_by_ai == 1 and rows[2].unanswered_text is None


def test_summary_aggregates_a_known_set_of_events(db):
    now = datetime(2031, 1, 10, 12, 0)  # isolated future window so other tests' rows don't interfere
    def ev(days_ago, **kw):
        base = dict(created_at=now - timedelta(days=days_ago, hours=1), kind="answer", channel="customer_portal", session_id="s1",
                    language="mr", answered_by_ai=1, handed_to_staff=0, prompt_tokens=1000, completion_tokens=200, llm_calls=1)
        return InteractionEvent(**{**base, **kw})
    db.add_all([
        ev(0, topic="Lost Passbook", elderly_mode=1),
        ev(1, topic="Lost Passbook", level_change="simpler", session_id="s2", language="hi"),
        ev(2, answered_by_ai=0, handed_to_staff=1, unanswered_text="Sukanya account?", session_id="s3"),
        ev(3, answered_by_ai=0, handed_to_staff=1, unanswered_text="sukanya account", session_id="s3"),
        ev(1, kind="eligibility", assets_json='["gold"]', matched_json='["gold_loan"]', estimated_amount_inr=150000, session_id="s4"),
        ev(9, topic="Lost Passbook"),  # previous period
    ])
    db.commit()

    s = analytics.summary(db, days=7, now=now)
    k = s["kpis"]
    assert k["questions"] == 4 and k["conversations"] == 4
    assert k["answered_by_ai_pct"] == 50 and k["handed_to_staff"] == 2 and k["didnt_understand"] == 1
    assert k["eligibility_checks"] == 1 and k["loan_pipeline_inr"] == 150000
    assert k["previous_questions"] == 1
    assert s["top_topics"][0] == {"topic": "Lost Passbook", "count": 2, "previous": 1, "didnt_understand": 1}
    assert s["unanswered"][0]["count"] == 2  # both wordings grouped
    assert s["eligibility"]["top_schemes"][0]["name"] == "Gold Loan"
    assert s["languages"] == {"mr": 3, "hi": 1}
    assert len(s["daily"]) == 7 and sum(d["questions"] for d in s["daily"]) == 4
    assert s["daily"][-1]["date"] == "2031-01-10"  # branch-local (IST) today
    assert k["ai_cost_inr"] > 0 and s["cost"]["prompt_tokens"] == 5000


def test_days_follow_branch_time_zone(db):
    # 20:00 UTC on 1 Mar is 01:30 on 2 Mar in India: it must count as "today" on 2 Mar.
    now = datetime(2032, 3, 1, 20, 30)
    db.add(InteractionEvent(created_at=datetime(2032, 3, 1, 20, 0), kind="answer", channel="customer_portal", session_id="tz",
                            language="mr", answered_by_ai=1))
    db.commit()
    s = analytics.summary(db, days=1, now=now)
    assert s["daily"] == [{"date": "2032-03-02", "questions": 1, "answered_by_ai": 1, "handed_to_staff": 0, "eligibility_checks": 0}]


def test_demo_data_can_be_added_and_removed(client):
    before = client.get("/api/dashboard/summary", headers=STAFF).json()["demo_events"]
    created = client.post("/api/dashboard/demo-data", headers=STAFF).json()["created"]
    assert created > 100
    s = client.get("/api/dashboard/summary", headers=STAFF).json()
    assert s["demo_events"] >= created > 0 and s["kpis"]["questions"] > 0 and s["unanswered"]
    removed = client.delete("/api/dashboard/demo-data", headers=STAFF).json()["removed"]
    assert removed >= created
    assert client.get("/api/dashboard/summary", headers=STAFF).json()["demo_events"] == 0
    assert before >= 0


def test_dashboard_is_staff_only(client):
    token = client.post("/api/customer/session/start", json={"language": "mr"}).json()["customer_token"]
    assert client.get("/api/dashboard/summary").status_code == 401
    assert client.get("/api/dashboard/summary", headers={"Authorization": f"Bearer {token}"}).status_code == 403


def test_customer_chat_is_recorded(client, db):
    s = client.post("/api/customer/session/start", json={"language": "hi"}).json()
    fake = {"reply_local": "x", "reply_english": "x", "spoken_response": "x", "sources": [{"topic": "Branch Working Hours and Holidays", "doc_id": "KB043", "chunk_index": 0, "score": 0.7}],
            "confidence": 0.7, "grounded": True}
    with patch("api.customer.ai_orchestrator.handle_customer_query", return_value=fake):
        client.post("/api/customer/chat", headers={"Authorization": f"Bearer {s['customer_token']}"},
                    json={"session_id": s["session_id"], "text": "bank kab khulta hai", "language": "hi", "elderly_mode": True})
    row = db.query(InteractionEvent).filter_by(session_id=s["session_id"]).one()
    assert (row.channel, row.topic, row.elderly_mode, row.answered_by_ai) == ("customer_portal", "Branch Working Hours and Holidays", 1, 1)
