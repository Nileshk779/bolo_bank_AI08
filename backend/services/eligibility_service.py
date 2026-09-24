"""
Loan / scheme eligibility pre-check.

Given what the customer owns (gold, land, a house, a fixed deposit), their
work, what they need the money for and their age, this service lists the
schemes from data/loan_schemes.json they MAY qualify for.

Deliberately rule-based, not LLM-based: eligibility is a yes/no question
over explicit criteria, so the answer must be reproducible and explainable
("you matched because you own land and are a farmer"), never generated.

Human-in-the-loop is preserved: the result is a pre-check. Every match is
framed as "may be eligible — staff will confirm", estimates are indicative
only, and nothing here can sanction, approve or book a loan.

The response is language-neutral: reasons and documents are returned as
codes the frontend localizes, and only scheme names/summaries (stored per
language in the catalogue) are resolved here.
"""
import json
import re
from functools import lru_cache
from typing import Any

from services.data_service import DATA_DIR

SCHEMES_PATH = DATA_DIR / "loan_schemes.json"

ASSET_TYPES = ("gold", "land", "house", "fd")
OCCUPATIONS = ("farmer", "business", "salaried", "pensioner", "student", "other")
PURPOSES = ("farming", "business", "education", "home", "medical", "personal", "not_sure")


@lru_cache(maxsize=1)
def load_catalogue() -> dict:
    with SCHEMES_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def _owned_assets(assets: dict) -> set[str]:
    owned = set()
    if (assets.get("gold_grams") or 0) > 0:
        owned.add("gold")
    if (assets.get("land_acres") or 0) > 0:
        owned.add("land")
    if assets.get("house"):
        owned.add("house")
    if (assets.get("fd_amount") or 0) > 0:
        owned.add("fd")
    return owned


def _estimate(scheme: dict, assets: dict, rates: dict) -> dict | None:
    est = scheme.get("estimate")
    if not est:
        return None
    if est["method"] == "gold_value":
        value = assets["gold_grams"] * rates["gold_22k_per_gram_inr"]
        return {
            "max_amount_inr": int(round(value * est["ratio"], -2)),
            "basis": "gold_value",
            "ratio": est["ratio"],
            "rate_per_gram_inr": rates["gold_22k_per_gram_inr"],
            "rate_as_of": rates["as_of"],
        }
    if est["method"] == "fd_value":
        return {
            "max_amount_inr": int(round(assets["fd_amount"] * est["ratio"], -2)),
            "basis": "fd_value",
            "ratio": est["ratio"],
        }
    return None


def evaluate_scheme(scheme: dict, assets: dict, occupation: str, purpose: str, age: int) -> dict | None:
    """Checks one scheme for one profile (used by scheme_alert_service)."""
    return _evaluate(scheme, _owned_assets(assets), assets, occupation, purpose, age)


def _evaluate(scheme: dict, owned: set[str], assets: dict, occupation: str, purpose: str, age: int) -> dict | None:
    """Returns the match (with reasons) or None if any hard rule fails."""
    rules = scheme["rules"]
    reasons: list[dict[str, Any]] = []

    needed = rules.get("collateral_any") or []
    if needed:
        have = [a for a in needed if a in owned]
        if not have:
            return None
        asset = have[0]
        params = {
            "gold": {"grams": assets.get("gold_grams")},
            "land": {"acres": assets.get("land_acres")},
            "house": {},
            "fd": {"amount": assets.get("fd_amount")},
        }[asset]
        reasons.append({"code": f"asset_{asset}", "params": params})
    else:
        reasons.append({"code": "no_collateral", "params": {}})

    occupations = rules.get("occupations")
    if occupations is not None:
        if occupation not in occupations:
            return None
        reasons.append({"code": "occupation", "params": {"occupation": occupation}})

    if rules.get("min_age") is not None and age < rules["min_age"]:
        return None
    if rules.get("max_age") is not None and age > rules["max_age"]:
        return None
    if rules.get("min_age", 0) >= 60:
        reasons.append({"code": "senior", "params": {}})
    else:
        reasons.append({"code": "age_ok", "params": {}})

    purposes = rules.get("purposes")
    if purposes is not None and purpose != "not_sure":
        if purpose not in purposes:
            return None
        reasons.append({"code": "purpose", "params": {"purpose": purpose}})

    return {
        # "likely" only when the customer told us the purpose and it matched;
        # an unknown purpose means staff need to confirm fit.
        "status": "likely" if purpose != "not_sure" or purposes is None else "possible",
        "reasons": reasons,
    }


def check_eligibility(assets: dict, occupation: str, purpose: str, age: int, language: str, extra_schemes: list[dict] | None = None) -> dict:
    """`extra_schemes` are staff-approved schemes from the daily update
    (scheme_update_service.get_approved_schemes), in the same shape as the
    catalogue entries plus an `added_on` date."""
    catalogue = load_catalogue()
    rates = catalogue["reference_rates"]
    owned = _owned_assets(assets)

    matches = []
    for scheme in [*catalogue["schemes"], *(extra_schemes or [])]:
        result = _evaluate(scheme, owned, assets, occupation, purpose, age)
        if not result:
            continue
        matches.append(
            {
                "scheme_id": scheme["id"],
                "kind": scheme["kind"],
                "name": scheme["name"].get(language) or scheme["name"]["en"],
                "name_english": scheme["name"]["en"],
                "summary": scheme["summary"].get(language) or scheme["summary"]["en"],
                "status": result["status"],
                "collateral_free": not scheme["rules"].get("collateral_any"),
                "reasons": result["reasons"],
                "estimate": _estimate(scheme, assets, rates),
                "documents": scheme["documents"],
                "source": scheme["source"],
                "is_new": "added_on" in scheme,
                "added_on": scheme.get("added_on"),
            }
        )

    # Likely matches first; within those, newly approved schemes (the ones
    # customers are least likely to know about), then those with a concrete
    # estimate, then government schemes.
    matches.sort(key=lambda m: (m["status"] != "likely", not m["is_new"], m["estimate"] is None, m["kind"] != "government_scheme"))

    return {
        "matches": matches,
        "catalogue_version": catalogue["catalogue_version"],
        "requires_human_review": True,
    }


def describe_profile_english(assets: dict, occupation: str, purpose: str, age: int) -> str:
    """Plain English line for the staff-facing session log."""
    owned = []
    if assets.get("gold_grams"):
        owned.append(f"gold ~{assets['gold_grams']:g} g")
    if assets.get("land_acres"):
        owned.append(f"land ~{assets['land_acres']:g} acres")
    if assets.get("house"):
        owned.append("house/property")
    if assets.get("fd_amount"):
        owned.append(f"FD ~Rs {assets['fd_amount']:,}")
    return (
        f"Loan eligibility check — owns: {', '.join(owned) or 'nothing to pledge'}; "
        f"work: {occupation}; purpose: {purpose.replace('_', ' ')}; age ~{age}."
    )


# Words that mean the customer is asking about loans/schemes, in the five
# supported languages. Used only to OFFER the eligibility checker in the
# chat UI — it never changes the chat answer itself.
_LOAN_INTEREST = re.compile(
    r"\b(loan|loans|scheme|schemes|eligib\w*|borrow|mortgage)\b"
    r"|लोन|ऋण|कर्ज|क़र्ज़|कर्ज़|योजना|गिरवी|तारण"
    r"|ಸಾಲ|ಯೋಜನೆ|ಅಡಮಾನ"
    r"|రుణ|అప్పు|పథకం|తాకట్టు",
    re.IGNORECASE,
)


def detect_loan_interest(text: str) -> bool:
    return bool(_LOAN_INTEREST.search(text or ""))
