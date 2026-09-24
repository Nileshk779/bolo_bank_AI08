"""
Branch manager dashboard: records what happens in the branch and summarises it.

Recording (called by the chat, Copilot and eligibility endpoints):
    record_answer()       one answered question — topic, language, whether the
                          AI answered or handed over to staff, "didn't
                          understand" follow-ups, AI token usage
    record_eligibility()  one loan eligibility check — asset types, matched
                          schemes, best loan estimate

Only counts-level facts are stored. The one piece of text kept is the
question the AI could NOT answer (after redacting sensitive-looking values),
so the manager can see which topics the knowledge base is missing.

summary() turns the events plus scheme-review data into the dashboard.
Demo data (is_demo=1) can be generated for presentations and removed again.
"""
import json
import random
import re
from collections import Counter
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from core.config import settings
from database.models import InteractionEvent, SchemeAlert, SchemeDraft
from services.eligibility_service import load_catalogue
from services.llm_service import tracked_usage
from services.response_privacy_service import redact_sensitive_values


# ------------------------------------------------------------ recording --- #
def record_answer(db: Session, *, channel: str, session_id: str, language: str, question: str, result: dict,
                  level_change: str | None = None, elderly_mode: bool = False) -> None:
    sources = result.get("sources") or []
    top = sources[0] if sources else None
    top = top if isinstance(top, dict) else (top.model_dump() if top else None)
    account_query = not sources and result.get("confidence") is None and bool(result.get("sensitive"))
    answered = (bool(result.get("grounded")) or account_query) and not result.get("requires_human_review")
    usage = tracked_usage()
    db.add(InteractionEvent(
        kind="answer", channel=channel, session_id=session_id, language=language, elderly_mode=int(bool(elderly_mode)),
        topic=top["topic"] if top else None, doc_id=top["doc_id"] if top else None, confidence=result.get("confidence"),
        answered_by_ai=int(answered), handed_to_staff=int(not answered), account_query=int(account_query),
        level_change=level_change,
        unanswered_text=None if (result.get("grounded") or account_query) else redact_sensitive_values(question or "").safe_text[:300],
        llm_calls=usage["llm_calls"], prompt_tokens=usage["prompt_tokens"], completion_tokens=usage["completion_tokens"],
    ))
    db.commit()


def record_eligibility(db: Session, *, session_id: str, language: str, assets: dict, result: dict) -> None:
    owned = [a for a, present in (("gold", assets.get("gold_grams")), ("land", assets.get("land_acres")),
                                  ("house", assets.get("house")), ("fd", assets.get("fd_amount"))) if present]
    estimates = [m["estimate"]["max_amount_inr"] for m in result["matches"] if m.get("estimate")]
    db.add(InteractionEvent(
        kind="eligibility", channel="customer_portal", session_id=session_id, language=language,
        answered_by_ai=1, assets_json=json.dumps(owned), matched_json=json.dumps([m["scheme_id"] for m in result["matches"]]),
        estimated_amount_inr=max(estimates) if estimates else None,
    ))
    db.commit()


# ---------------------------------------------------------------- summary --- #
def _cost_inr(prompt_tokens: int, completion_tokens: int) -> float:
    usd = prompt_tokens / 1e6 * settings.LLM_PRICE_INPUT_PER_M_USD + completion_tokens / 1e6 * settings.LLM_PRICE_OUTPUT_PER_M_USD
    return usd * settings.USD_TO_INR


def _scheme_names(db: Session) -> dict[str, str]:
    names = {s["id"]: s["name"]["en"] for s in load_catalogue()["schemes"]}
    for d in db.query(SchemeDraft).filter(SchemeDraft.status == "approved"):
        s = json.loads(d.draft_json)
        names[s.get("id")] = s.get("name", {}).get("en", s.get("id"))
    return names


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[?!.,।]", "", text.lower())).strip()


def summary(db: Session, days: int = 7, now: datetime | None = None) -> dict:
    """`days` whole calendar days in the branch's time zone, ending today
    (days=1 is "today"); the previous period of equal length gives trends.
    Timestamps are stored in UTC and shifted by BRANCH_UTC_OFFSET_MINUTES."""
    now = now or datetime.utcnow()
    offset = timedelta(minutes=settings.BRANCH_UTC_OFFSET_MINUTES)
    local_today = (now + offset).replace(hour=0, minute=0, second=0, microsecond=0)
    start = local_today - timedelta(days=days - 1) - offset
    prev_start = start - timedelta(days=days)
    rows = db.query(InteractionEvent).filter(InteractionEvent.created_at >= prev_start, InteractionEvent.created_at <= now).all()
    cur = [r for r in rows if r.created_at >= start]
    prev = [r for r in rows if r.created_at < start]
    answers = [r for r in cur if r.kind == "answer"]
    checks = [r for r in cur if r.kind == "eligibility"]

    # --- daily series (every day in the period, including empty ones)
    by_day: dict[str, dict] = {}
    for i in range(days - 1, -1, -1):
        d = (local_today - timedelta(days=i)).date().isoformat()
        by_day[d] = {"date": d, "questions": 0, "answered_by_ai": 0, "handed_to_staff": 0, "eligibility_checks": 0}
    for r in cur:
        day = by_day.get((r.created_at + offset).date().isoformat())
        if not day:
            continue
        if r.kind == "answer":
            day["questions"] += 1
            day["answered_by_ai"] += r.answered_by_ai
            day["handed_to_staff"] += r.handed_to_staff
        else:
            day["eligibility_checks"] += 1

    # --- topics, with trend vs the previous period and "didn't understand" counts
    confused = {"simpler", "reexplain"}
    topic_now = Counter(r.topic for r in answers if r.topic)
    topic_prev = Counter(r.topic for r in prev if r.kind == "answer" and r.topic)
    confusion = Counter(r.topic for r in answers if r.topic and r.level_change in confused)
    top_topics = [{"topic": t, "count": c, "previous": topic_prev.get(t, 0), "didnt_understand": confusion.get(t, 0)}
                  for t, c in topic_now.most_common(8)]

    # --- questions the AI could not answer, grouped by wording
    groups: dict[str, dict] = {}
    for r in sorted((r for r in answers if r.unanswered_text), key=lambda r: r.created_at):
        key = _normalise(r.unanswered_text)
        g = groups.setdefault(key, {"text": r.unanswered_text, "count": 0, "languages": set(), "last_at": None})
        g["count"] += 1
        g["languages"].add(r.language)
        g["last_at"] = r.created_at.isoformat()
    unanswered = [{**g, "languages": sorted(g["languages"])} for g in groups.values()]
    unanswered.sort(key=lambda g: g["last_at"], reverse=True)  # most recent first...
    unanswered.sort(key=lambda g: g["count"], reverse=True)  # ...within each count (stable sort)
    unanswered = unanswered[:10]

    # --- eligibility / loan leads
    names = _scheme_names(db)
    scheme_counts = Counter(s for r in checks for s in json.loads(r.matched_json or "[]"))
    asset_counts = Counter(a for r in checks for a in json.loads(r.assets_json or "[]"))
    pipeline = sum(r.estimated_amount_inr or 0 for r in checks)

    # --- scheme review and customer matches
    approved = db.query(SchemeDraft).filter(SchemeDraft.status == "approved", SchemeDraft.reviewed_at >= start).all()
    hours = [(d.reviewed_at - d.fetched_at).total_seconds() / 3600 for d in approved if d.reviewed_at and d.fetched_at]
    alert_counts = Counter(a.status for a in db.query(SchemeAlert))

    # --- AI cost
    p_tok = sum(r.prompt_tokens or 0 for r in cur)
    c_tok = sum(r.completion_tokens or 0 for r in cur)
    cost = _cost_inr(p_tok, c_tok)
    sessions = {r.session_id for r in cur}
    ai_answers = sum(r.answered_by_ai for r in answers)
    elderly_base = [r for r in answers if r.channel != "copilot"]

    return {
        "period": {"days": days, "start": start.isoformat(), "end": now.isoformat()},
        "kpis": {
            "conversations": len(sessions),
            "questions": len(answers),
            "answered_by_ai_pct": round(100 * ai_answers / len(answers)) if answers else None,
            "handed_to_staff": sum(r.handed_to_staff for r in answers),
            "didnt_understand": sum(1 for r in answers if r.level_change in confused),
            "elderly_mode_pct": round(100 * sum(r.elderly_mode for r in elderly_base) / len(elderly_base)) if elderly_base else None,
            "eligibility_checks": len(checks),
            "loan_pipeline_inr": pipeline,
            "ai_cost_inr": round(cost, 2),
            "ai_cost_per_conversation_inr": round(cost / len(sessions), 3) if sessions else None,
            "previous_questions": sum(1 for r in prev if r.kind == "answer"),
        },
        "daily": list(by_day.values()),
        "languages": dict(Counter(r.language for r in answers).most_common()),
        "channels": dict(Counter(r.channel for r in answers).most_common()),
        "top_topics": top_topics,
        "unanswered": unanswered,
        "eligibility": {
            "checks": len(checks),
            "assets": dict(asset_counts.most_common()),
            "top_schemes": [{"scheme_id": s, "name": names.get(s, s), "count": c} for s, c in scheme_counts.most_common(6)],
            "pipeline_inr": pipeline,
        },
        "schemes": {
            "approved_in_period": len(approved),
            "avg_hours_to_approve": round(sum(hours) / len(hours), 1) if hours else None,
            "pending_review": db.query(SchemeDraft).filter(SchemeDraft.status == "pending").count(),
            "matches": {"to_contact": alert_counts.get("new", 0), "contacted": alert_counts.get("contacted", 0), "not_suitable": alert_counts.get("not_suitable", 0)},
        },
        "cost": {
            "llm_calls": sum(r.llm_calls or 0 for r in cur), "prompt_tokens": p_tok, "completion_tokens": c_tok,
            "cost_inr": round(cost, 2),
            "cost_per_question_inr": round(cost / len(answers), 3) if answers else None,
            "assumptions": {
                "model": settings.GROQ_CHAT_MODEL,
                "input_usd_per_million_tokens": settings.LLM_PRICE_INPUT_PER_M_USD,
                "output_usd_per_million_tokens": settings.LLM_PRICE_OUTPUT_PER_M_USD,
                "usd_to_inr": settings.USD_TO_INR,
                "note": "Chat AI only; speech-to-text and text-to-speech are not included.",
            },
        },
        "demo_events": sum(1 for r in rows if r.is_demo),
    }


# -------------------------------------------------------------- demo data --- #
_DEMO_LANGS = [("mr", 45), ("hi", 25), ("kn", 12), ("te", 10), ("en", 8)]
_DEMO_TOPICS = [  # (doc_id, weight)
    ("KB019", 9), ("KB006", 8), ("KB030", 7), ("KB040", 7), ("KB003", 6), ("KB011", 6), ("KB024", 5), ("KB012", 5),
    ("KB038", 5), ("KB025", 4), ("KB031", 4), ("KB014", 3), ("KB005", 3), ("KB043", 3), ("KB041", 3), ("KB002", 3),
]
_DEMO_UNANSWERED = [
    ("Sukanya Samriddhi account kaise kholein", "hi", 5), ("लॉकरचे भाडे कधी भरायचे", "mr", 4),
    ("can I get a loan to buy a tractor through NABARD", "en", 3), ("ಹಳೆಯ ನೋಟುಗಳನ್ನು ಬದಲಾಯಿಸಬಹುದೇ", "kn", 2),
    ("पीपीएफ खाते उघडता येईल का", "mr", 3), ("క్రెడిట్ కార్డు కోసం ఎలా దరఖాస్తు చేయాలి", "te", 2),
]
_DEMO_ASSETS = [(["gold"], 10), (["gold", "land"], 5), (["land"], 4), (["house"], 3), (["fd"], 2), ([], 3)]


def generate_demo_data(db: Session, days: int = 14, seed: int = 7, now: datetime | None = None) -> int:
    """A realistic two weeks of branch activity (so trends have a previous
    period), all flagged is_demo=1. Returns the number of events created."""
    rng = random.Random(seed)
    now = now or datetime.utcnow()
    offset = timedelta(minutes=settings.BRANCH_UTC_OFFSET_MINUTES)
    local_now = now + offset
    docs = {s["id"]: s for s in json.load(open(_kb_path(), encoding="utf-8"))}
    pick = lambda pairs: rng.choices([p[0] for p in pairs], weights=[p[-1] for p in pairs])[0]  # noqa: E731
    events = []
    for day in range(days):
        date = local_now - timedelta(days=day)  # branch-local; converted to UTC below
        growth = 1 + 0.04 * (days - day)  # gently rising usage
        for _ in range(int(rng.randint(18, 30) * growth)):
            when = date.replace(hour=rng.randint(10, 15), minute=rng.randint(0, 59), second=0, microsecond=0) - offset
            if when > now:
                when = now - timedelta(minutes=rng.randint(1, 120))
            session = f"demo-{day}-{rng.randint(1, 18)}"
            lang = pick(_DEMO_LANGS)
            channel = rng.choices(["customer_portal", "staff_session", "copilot"], weights=[60, 30, 10])[0]
            elderly = int(channel != "copilot" and rng.random() < 0.55)
            prompt, completion = rng.randint(1100, 1900), rng.randint(150, 420)
            if rng.random() < 0.12:  # the AI could not answer -> staff
                text, lang, _ = rng.choices(_DEMO_UNANSWERED, weights=[u[2] for u in _DEMO_UNANSWERED])[0]
                events.append(InteractionEvent(created_at=when, kind="answer", channel=channel, session_id=session, language=lang,
                                               elderly_mode=elderly, confidence=round(rng.uniform(0.2, 0.41), 3), answered_by_ai=0,
                                               handed_to_staff=1, unanswered_text=text, is_demo=1))
                continue
            doc_id = pick(_DEMO_TOPICS)
            review = rng.random() < 0.05
            level = rng.choices([None, "simpler", "reexplain", "more_detail"], weights=[86, 7, 2, 5])[0]
            events.append(InteractionEvent(created_at=when, kind="answer", channel=channel, session_id=session, language=lang,
                                           elderly_mode=elderly, topic=docs[doc_id]["title"], doc_id=doc_id,
                                           confidence=round(rng.uniform(0.45, 0.85), 3), answered_by_ai=int(not review),
                                           handed_to_staff=int(review), level_change=level, llm_calls=1,
                                           prompt_tokens=prompt, completion_tokens=completion, is_demo=1))
        for _ in range(int(rng.randint(2, 7) * growth)):
            owned = pick(_DEMO_ASSETS)
            matched, estimate = [], None
            if "gold" in owned:
                grams = rng.choice([10, 20, 25, 40, 50, 100])
                estimate = int(grams * load_catalogue()["reference_rates"]["gold_22k_per_gram_inr"] * 0.75)
                matched += ["gold_loan"] + (["agri_gold_loan"] if "land" in owned else [])
            if "land" in owned:
                matched += ["kisan_credit_card", "farm_investment_loan"]
            if "house" in owned:
                matched += ["loan_against_property"] + (["reverse_mortgage"] if rng.random() < 0.5 else [])
            if "fd" in owned:
                matched += ["loan_against_fd"]
            if not owned:
                matched += rng.choice([["pm_mudra"], ["pensioner_loan"], ["education_loan"]])
            when = date.replace(hour=rng.randint(10, 15), minute=rng.randint(0, 59), second=0, microsecond=0) - offset
            when = min(when, now - timedelta(minutes=rng.randint(1, 120)))
            events.append(InteractionEvent(created_at=when,
                                           kind="eligibility", channel="customer_portal", session_id=f"demo-{day}-{rng.randint(1, 18)}",
                                           language=pick(_DEMO_LANGS), answered_by_ai=1, assets_json=json.dumps(owned),
                                           matched_json=json.dumps(matched), estimated_amount_inr=estimate, is_demo=1))
    db.add_all(events)
    db.commit()
    return len(events)


def remove_demo_data(db: Session) -> int:
    n = db.query(InteractionEvent).filter(InteractionEvent.is_demo == 1).delete()
    db.commit()
    return n


def _kb_path():
    from core.config import KNOWLEDGE_BASE_PATH

    return KNOWLEDGE_BASE_PATH
