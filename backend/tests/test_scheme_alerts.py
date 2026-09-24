"""
Matching newly approved schemes to existing customers
(services/scheme_alert_service.py, /api/schemes/alerts).
"""
import json
from datetime import date

import pytest

from auth.security import create_access_token
from database.models import SchemeAlert
from database.session import SessionLocal
from services import scheme_alert_service as alerts
from services import scheme_update_service as svc
from tests.test_scheme_updates import FakeFeed, drafts_for

STAFF = {"Authorization": f"Bearer {create_access_token('staff')}"}


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.close()


def preset(feed_id):
    with svc.FEED_PATH.open(encoding="utf-8") as f:
        return next(i for i in json.load(f)["items"] if i["feed_id"] == feed_id)["demo_extraction"]


def matched_ids(scheme):
    return sorted(m["customer"]["customer_id"] for m in alerts.match_customers(scheme))


def test_senior_gold_loan_matches_senior_gold_owners_with_a_matching_need():
    # Ramesh 68, Meena 72, Savitri 66 own gold and mentioned medical needs.
    # Lakshmi (61, gold) only mentioned farming, so the purpose doesn't match.
    assert matched_ids(preset("demo-2026-09-20-senior-gold")) == ["CUST001", "CUST002", "CUST004"]


def test_age_limit_excludes_customers():
    # Home repair loan is capped at 70: Meena (72) wants home help but is excluded.
    assert "CUST002" not in matched_ids(preset("demo-2026-10-01-home-repair"))


def test_customers_without_consent_are_never_matched():
    scheme = preset("demo-2026-10-01-home-repair")
    scheme["rules"] = {"collateral_any": [], "occupations": None, "purposes": None, "min_age": 18, "max_age": None}
    ids = matched_ids(scheme)
    assert "CUST005" not in ids  # Vijay has offers_consent=false
    assert len(ids) == 5


def test_approval_creates_alerts_with_local_language_message(db):
    svc.run_update(db, today=date(2026, 9, 24), feed=FakeFeed("a1"))
    solar = drafts_for(db, "a1")["demo-2026-09-23-solar-pump"]
    svc.approve(db, solar.id, "staff")

    rows = db.query(SchemeAlert).filter_by(draft_id=solar.id).all()
    assert [r.customer_id for r in rows] == ["CUST001"]
    a = alerts.serialize_alert(rows[0])
    assert a["language"] == "mr"
    assert a["message_local"].startswith("नमस्कार Ramesh.")
    assert "सौर पंप कर्ज" in a["message_local"]
    assert "Owns about 3 acres of land" in a["reasons"]
    assert a["staff_checks"]
    # The message never contains account data.
    assert "12450" not in a["message_local"] and "4321" not in a["message_local"]


def test_alerts_are_not_duplicated_on_rescan(db):
    svc.run_update(db, today=date(2026, 9, 24), feed=FakeFeed("a2"))
    kcc = drafts_for(db, "a2")["demo-2026-09-22-kcc-dairy"]
    svc.approve(db, kcc.id, "staff")
    before = db.query(SchemeAlert).filter_by(draft_id=kcc.id).count()
    assert before == 2  # Ramesh and Lakshmi (farmers)
    alerts.rescan_all(db)
    assert db.query(SchemeAlert).filter_by(draft_id=kcc.id).count() == before


def test_staff_checks_travel_with_the_alert(db):
    svc.run_update(db, today=date(2026, 9, 24), feed=FakeFeed("a3"))
    shg = drafts_for(db, "a3")["demo-2026-09-24-shg-microloan"]
    svc.save_edits(db, shg.id, {"rules": {"occupations": ["business"]}, "documents": ["id_proof", "photo"]})
    svc.approve(db, shg.id, "staff")
    a = db.query(SchemeAlert).filter_by(draft_id=shg.id).one()
    # The rules can't check gender — staff see it so they can dismiss this one.
    assert a.customer_id == "CUST003"
    assert "Applicant must be a woman" in json.loads(a.staff_checks_json)


def test_staff_checks_are_editable_and_validated(db):
    svc.run_update(db, today=date(2026, 9, 24), feed=FakeFeed("a4"))
    d = drafts_for(db, "a4")["demo-2026-09-20-senior-gold"]
    svc.save_edits(db, d.id, {"staff_checks": ["  Check pension slip  ", ""]})
    assert json.loads(d.draft_json)["staff_checks"] == ["Check pension slip"]
    svc.save_edits(db, d.id, {"staff_checks": ["x" * 300]})
    assert any("Staff checks" in i for i in json.loads(d.validation_issues))


# ------------------------------------------------------------------ API --- #
def test_alert_api_flow(client, db):
    svc.run_update(db, today=date(2026, 9, 24), feed=FakeFeed("a5"))
    senior = drafts_for(db, "a5")["demo-2026-09-20-senior-gold"]
    res = client.post(f"/api/schemes/updates/{senior.id}/approve", headers=STAFF, json={})
    assert res.json()["customers_matched"] == 3

    new = [a for a in client.get("/api/schemes/alerts", headers=STAFF).json() if a["scheme_id"] == "senior_gold_loan_a5"]
    assert len(new) == 3
    meena = next(a for a in new if a["customer_id"] == "CUST002")
    assert meena["language"] == "hi"

    res = client.post(f"/api/schemes/alerts/{meena['id']}", headers=STAFF, json={"status": "contacted", "note": "called, visiting Monday"})
    assert res.status_code == 200 and res.json()["handled_by"] == "staff"
    contacted = client.get("/api/schemes/alerts?status=contacted", headers=STAFF).json()
    assert any(a["id"] == meena["id"] for a in contacted)

    assert client.post("/api/schemes/alerts/rescan", headers=STAFF).status_code == 200
    assert client.post("/api/schemes/alerts/999999", headers=STAFF, json={"status": "contacted"}).status_code == 404
    assert client.get("/api/schemes/updates/status", headers=STAFF).json()["counts"]["alerts_new"] >= 2


def test_alert_routes_require_staff(client):
    token = client.post("/api/customer/session/start", json={"language": "mr"}).json()["customer_token"]
    assert client.get("/api/schemes/alerts").status_code == 401
    assert client.get("/api/schemes/alerts", headers={"Authorization": f"Bearer {token}"}).status_code == 403


# ------------------------------------------- customer "new schemes" note --- #
def test_customer_new_schemes_lists_only_recent_approved_in_their_language(client, db):
    svc.run_update(db, today=date(2026, 9, 24), feed=FakeFeed("n1"))
    d = drafts_for(db, "n1")
    svc.approve(db, d["demo-2026-09-23-solar-pump"].id, "staff")  # approved -> announced
    # pending KCC dairy draft must NOT be announced

    res = client.get("/api/customer/new-schemes?language=kn")
    assert res.status_code == 200  # public: shown before a session starts
    items = {i["scheme_id"]: i for i in res.json()}
    assert "solar_pump_loan_n1" in items
    assert "kcc_animal_husbandry_n1" not in items
    assert items["solar_pump_loan_n1"]["name"] == "ಸೌರ ಪಂಪ್ ಸಾಲ (PM-KUSUM ಸಂಬಂಧಿತ)"
    assert set(items["solar_pump_loan_n1"]) == {"scheme_id", "kind", "name", "summary", "collateral_free", "added_on", "valid_until"}


def test_customer_new_schemes_rejects_unknown_language(client):
    assert client.get("/api/customer/new-schemes?language=xx").status_code == 400


def test_old_approvals_are_no_longer_announced(client, db, monkeypatch):
    from core.config import settings

    monkeypatch.setattr(settings, "NEW_SCHEME_DAYS", -1)  # everything counts as old
    assert client.get("/api/customer/new-schemes?language=en").json() == []
