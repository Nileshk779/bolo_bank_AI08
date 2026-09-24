"""
Daily scheme updates with staff approval (services/scheme_update_service.py,
api/schemes.py) and the customer-token / staff-route separation fix.
"""
import copy
import json
from datetime import date
from unittest.mock import patch

import pytest

from auth.security import create_access_token
from database.models import SchemeDraft
from database.session import SessionLocal
from services import scheme_update_service as svc
from services.eligibility_service import check_eligibility

STAFF = {"Authorization": f"Bearer {create_access_token('staff')}"}


def feed_items():
    with svc.FEED_PATH.open(encoding="utf-8") as f:
        return json.load(f)["items"]


class FakeFeed:
    """Feed with unique ids per test so tests sharing the session DB don't collide."""

    def __init__(self, suffix, items=None):
        self.items = []
        for item in copy.deepcopy(items or feed_items()):
            item["feed_id"] += f"-{suffix}"
            item["demo_extraction"]["id"] += f"_{suffix}"
            self.items.append(item)

    def fetch(self, today):
        return [i for i in self.items if date.fromisoformat(i["published_on"]) <= today]


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.close()


def drafts_for(db, suffix):
    return {d.feed_id.removesuffix(f"-{suffix}"): d for d in db.query(SchemeDraft) if d.feed_id.endswith(f"-{suffix}")}


# ------------------------------------------------------------- the job --- #
def test_run_only_picks_up_items_published_by_today(db):
    feed = FakeFeed("t1")
    run = svc.run_update(db, today=date(2026, 9, 24), feed=feed)
    assert run.items_seen == 4 and run.new_drafts == 4 and run.error is None
    assert "demo-2026-10-01-home-repair" not in drafts_for(db, "t1")

    later = svc.run_update(db, today=date(2026, 10, 1), feed=feed)
    assert later.new_drafts == 1  # only the newly published item
    assert all(d.status == "pending" for d in drafts_for(db, "t1").values())


def test_run_is_idempotent(db):
    feed = FakeFeed("t2")
    svc.run_update(db, today=date(2026, 9, 24), feed=feed)
    again = svc.run_update(db, today=date(2026, 9, 24), feed=feed)
    assert again.new_drafts == 0


def test_bad_extraction_is_flagged_for_staff(db):
    svc.run_update(db, today=date(2026, 9, 24), feed=FakeFeed("t3"))
    shg = drafts_for(db, "t3")["demo-2026-09-24-shg-microloan"]
    issues = json.loads(shg.validation_issues)
    assert any("shg_member" in i for i in issues)
    assert any("shg_certificate" in i for i in issues)


def test_llm_extraction_used_when_enabled_and_falls_back_on_error():
    item = feed_items()[0]
    with patch.object(svc.settings, "SCHEME_EXTRACTION_MODE", "llm"), patch.object(svc.settings, "GROQ_API_KEY", "x"):
        with patch("services.llm_service.chat_completion", return_value=json.dumps(item["demo_extraction"])):
            draft, method = svc.extract(item)
        assert method == "llm" and draft["id"] == "senior_gold_loan"

        with patch("services.llm_service.chat_completion", side_effect=RuntimeError("quota")):
            draft, method = svc.extract(item)
        assert method == "preset_after_llm_error" and draft["id"] == "senior_gold_loan"


def test_validation_catches_common_problems():
    draft = copy.deepcopy(feed_items()[0]["demo_extraction"])
    draft["name"]["te"] = ""
    draft["rules"]["min_age"] = 80
    draft["rules"]["max_age"] = 70
    draft["estimate"] = {"method": "fd_value", "ratio": 0.9}
    issues = svc.validate(draft, {"senior_gold_loan"})
    text = " ".join(issues)
    assert "already exists" in text
    assert "te" in text
    assert "greater than maximum" in text
    assert "does not match the collateral" in text


def test_validation_never_raises_on_malformed_llm_output():
    assert svc.validate({"rules": {"min_age": "sixty"}, "estimate": {"ratio": "abc", "method": "gold_value"}}, set())


# ------------------------------------------------ approval & customers --- #
def test_only_approved_schemes_reach_customers(db):
    svc.run_update(db, today=date(2026, 9, 24), feed=FakeFeed("t4"))
    solar = drafts_for(db, "t4")["demo-2026-09-23-solar-pump"]

    def solar_offered():
        r = check_eligibility({"land_acres": 2}, "farmer", "farming", 50, "mr", extra_schemes=svc.get_approved_schemes(db))
        return [m for m in r["matches"] if m["scheme_id"] == "solar_pump_loan_t4"]

    assert not solar_offered()
    svc.approve(db, solar.id, "staff", "checked with circular")
    match = solar_offered()
    assert match and match[0]["is_new"] and match[0]["name"] == "सौर पंप कर्ज (PM-KUSUM शी जोडलेले)"
    assert solar.reviewed_by == "staff"


def test_draft_with_issues_cannot_be_approved_until_fixed(db):
    svc.run_update(db, today=date(2026, 9, 24), feed=FakeFeed("t5"))
    shg = drafts_for(db, "t5")["demo-2026-09-24-shg-microloan"]
    with pytest.raises(svc.ReviewError) as exc:
        svc.approve(db, shg.id, "staff")
    assert exc.value.issues

    svc.save_edits(db, shg.id, {"rules": {"occupations": ["business", "other"]}, "documents": ["id_proof", "address_proof", "photo"]})
    assert json.loads(shg.validation_issues) == []
    svc.approve(db, shg.id, "staff")
    assert shg.status == "approved"


def test_expired_schemes_are_not_offered(db):
    feed = FakeFeed("t6")
    svc.run_update(db, today=date(2026, 10, 1), feed=feed)
    repair = drafts_for(db, "t6")["demo-2026-10-01-home-repair"]
    svc.approve(db, repair.id, "staff")
    ids = lambda day: [s["id"] for s in svc.get_approved_schemes(db, today=day)]
    assert "festive_home_repair_loan_t6" in ids(date(2026, 11, 15))
    assert "festive_home_repair_loan_t6" not in ids(date(2026, 11, 16))


def test_rejected_draft_cannot_be_reviewed_again(db):
    svc.run_update(db, today=date(2026, 9, 24), feed=FakeFeed("t7"))
    d = drafts_for(db, "t7")["demo-2026-09-22-kcc-dairy"]
    svc.reject(db, d.id, "staff", "duplicate of existing KCC")
    with pytest.raises(svc.ReviewError):
        svc.approve(db, d.id, "staff")


# ------------------------------------------------------------------ API --- #
def test_staff_api_flow(client):
    assert client.post("/api/schemes/updates/run", headers=STAFF).status_code == 200
    status = client.get("/api/schemes/updates/status", headers=STAFF).json()
    assert status["last_run"]["trigger"] == "manual"

    pending = client.get("/api/schemes/updates", headers=STAFF).json()
    senior = next(d for d in pending if d["feed_id"] == "demo-2026-09-20-senior-gold")
    res = client.post(f"/api/schemes/updates/{senior['id']}/approve", headers=STAFF, json={"note": "ok"})
    assert res.status_code == 200 and res.json()["status"] == "approved"
    assert client.post(f"/api/schemes/updates/{senior['id']}/approve", headers=STAFF, json={}).status_code == 409

    shg = next(d for d in pending if d["feed_id"] == "demo-2026-09-24-shg-microloan")
    res = client.post(f"/api/schemes/updates/{shg['id']}/approve", headers=STAFF, json={})
    assert res.status_code == 422 and res.json()["detail"]["issues"]

    names = [s["id"] for s in client.get("/api/schemes/catalogue", headers=STAFF).json()["schemes"]]
    assert "senior_gold_loan" in names


def test_customer_sees_approved_scheme_marked_new(client):
    session = client.post("/api/customer/session/start", json={"language": "hi"}).json()
    res = client.post(
        "/api/customer/eligibility",
        headers={"Authorization": f"Bearer {session['customer_token']}"},
        json={"session_id": session["session_id"], "assets": {"gold_grams": 20}, "occupation": "pensioner", "purpose": "medical", "age": 68},
    ).json()
    senior = [m for m in res["matches"] if m["scheme_id"] == "senior_gold_loan"]
    assert senior and senior[0]["is_new"] and senior[0]["name"] == "वरिष्ठ नागरिक गोल्ड लोन"


def test_scheme_routes_require_staff(client):
    assert client.get("/api/schemes/updates").status_code == 401


def test_customer_token_cannot_use_staff_routes(client):
    """Regression: customer-portal tokens (no login needed) were accepted by
    get_current_staff because both are signed with the same key."""
    token = client.post("/api/customer/session/start", json={"language": "mr"}).json()["customer_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/schemes/updates", headers=headers).status_code == 403
    assert client.get("/api/queue", headers=headers).status_code == 403
