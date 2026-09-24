"""
Loan / scheme eligibility pre-check (services/eligibility_service.py and
POST /api/customer/eligibility).
"""
import pytest

from services.eligibility_service import check_eligibility, detect_loan_interest, load_catalogue


def ids(result):
    return [m["scheme_id"] for m in result["matches"]]


def test_catalogue_has_all_languages_for_every_scheme():
    for scheme in load_catalogue()["schemes"]:
        for lang in ("en", "hi", "mr", "kn", "te"):
            assert scheme["name"].get(lang), f"{scheme['id']} missing name[{lang}]"
            assert scheme["summary"].get(lang), f"{scheme['id']} missing summary[{lang}]"


def test_senior_farmer_with_gold_and_land_for_farming():
    r = check_eligibility({"gold_grams": 20, "land_acres": 2}, "farmer", "farming", 68, "mr")
    assert set(ids(r)) >= {"gold_loan", "agri_gold_loan", "kisan_credit_card", "farm_investment_loan"}
    assert "pm_mudra" not in ids(r)
    assert all(m["status"] == "likely" for m in r["matches"])
    kcc = next(m for m in r["matches"] if m["scheme_id"] == "kisan_credit_card")
    assert kcc["name"] == "किसान क्रेडिट कार्ड (KCC)"
    assert {"code": "asset_land", "params": {"acres": 2}} in kcc["reasons"]


def test_gold_estimate_uses_reference_rate_and_ratio():
    rate = load_catalogue()["reference_rates"]["gold_22k_per_gram_inr"]
    r = check_eligibility({"gold_grams": 10}, "other", "medical", 45, "en")
    gold = next(m for m in r["matches"] if m["scheme_id"] == "gold_loan")
    assert gold["estimate"]["max_amount_inr"] == round(10 * rate * 0.75, -2)


def test_kcc_age_limit():
    r = check_eligibility({"land_acres": 3}, "farmer", "farming", 80, "en")
    assert "kisan_credit_card" not in ids(r)


def test_land_without_farming_does_not_match_farm_schemes():
    r = check_eligibility({"land_acres": 3}, "salaried", "home", 40, "en")
    assert "kisan_credit_card" not in ids(r)
    assert "home_loan" in ids(r)


def test_reverse_mortgage_only_for_60_plus_home_owners():
    assert "reverse_mortgage" in ids(check_eligibility({"house": True}, "pensioner", "medical", 66, "en"))
    assert "reverse_mortgage" not in ids(check_eligibility({"house": True}, "pensioner", "medical", 55, "en"))
    assert "reverse_mortgage" not in ids(check_eligibility({}, "pensioner", "medical", 66, "en"))


def test_business_with_nothing_to_pledge_gets_mudra():
    r = check_eligibility({}, "business", "business", 35, "hi")
    assert ids(r) == ["pm_mudra"]
    assert r["matches"][0]["collateral_free"] is True


def test_not_sure_purpose_marks_purpose_specific_schemes_as_possible():
    r = check_eligibility({"gold_grams": 10, "land_acres": 1}, "farmer", "not_sure", 50, "en")
    by_id = {m["scheme_id"]: m for m in r["matches"]}
    assert by_id["gold_loan"]["status"] == "likely"
    assert by_id["kisan_credit_card"]["status"] == "possible"


def test_fd_estimate():
    r = check_eligibility({"fd_amount": 100000}, "other", "personal", 30, "en")
    fd = next(m for m in r["matches"] if m["scheme_id"] == "loan_against_fd")
    assert fd["estimate"]["max_amount_inr"] == 90000


def test_no_match_returns_empty_list():
    r = check_eligibility({}, "other", "farming", 30, "en")
    assert r["matches"] == []
    assert r["requires_human_review"] is True


@pytest.mark.parametrize(
    "text",
    ["Can I get a loan on my gold?", "मुझे लोन चाहिए", "मला कर्ज हवे आहे", "ನನಗೆ ಸಾಲ ಬೇಕು", "నాకు రుణం కావాలి", "any new scheme for farmers"],
)
def test_detect_loan_interest(text):
    assert detect_loan_interest(text)


def test_detect_loan_interest_ignores_unrelated():
    assert not detect_loan_interest("What are the branch working hours?")


# ---------------------------------------------------------------- API --- #
def _customer_session(client, language="mr"):
    data = client.post("/api/customer/session/start", json={"language": language}).json()
    return data["session_id"], {"Authorization": f"Bearer {data['customer_token']}"}


def test_eligibility_endpoint_returns_localized_matches(client):
    session_id, headers = _customer_session(client, "mr")
    res = client.post(
        "/api/customer/eligibility",
        headers=headers,
        json={"session_id": session_id, "assets": {"gold_grams": 20}, "occupation": "farmer", "purpose": "farming", "age": 68},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["requires_human_review"] is True
    names = [m["name"] for m in body["matches"]]
    assert "शेती सोने तारण कर्ज" in names


def test_eligibility_endpoint_requires_customer_token(client):
    res = client.post(
        "/api/customer/eligibility",
        json={"session_id": "x", "occupation": "farmer", "purpose": "farming", "age": 50},
    )
    assert res.status_code == 401


def test_eligibility_endpoint_rejects_other_session(client):
    _, headers = _customer_session(client)
    res = client.post(
        "/api/customer/eligibility",
        headers=headers,
        json={"session_id": "someone-else", "occupation": "farmer", "purpose": "farming", "age": 50},
    )
    assert res.status_code == 403


def test_eligibility_endpoint_validates_input(client):
    session_id, headers = _customer_session(client)
    res = client.post(
        "/api/customer/eligibility",
        headers=headers,
        json={"session_id": session_id, "occupation": "astronaut", "purpose": "farming", "age": 50},
    )
    assert res.status_code == 422
