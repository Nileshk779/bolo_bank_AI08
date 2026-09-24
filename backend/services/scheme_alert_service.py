"""
"This new scheme may suit these customers" alerts for staff.

When an employee approves a scheme from the daily update, every existing
customer who agreed to receive offers is checked against it with the same
rules the customer eligibility checker uses. Each match becomes an alert in
the Staff Portal with the reasons, the conditions the rules cannot check, and
a suggested message in the customer's own language.

Human-in-the-loop: nothing is sent to the customer automatically. A staff
member decides whether to contact them and records the outcome.
"""
import json
import logging
from datetime import datetime
from functools import lru_cache

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database.models import SchemeAlert, SchemeDraft
from services.data_service import DATA_DIR, get_customer
from services.eligibility_service import evaluate_scheme

logger = logging.getLogger("bolobank.scheme_alerts")

PROFILES_PATH = DATA_DIR / "customer_loan_profiles.json"
LANGUAGE_CODES = {"English": "en", "Hindi": "hi", "Marathi": "mr", "Kannada": "kn", "Telugu": "te"}

_GREETING = {
    "en": "Namaste {name}. A new scheme may help you: {scheme}.",
    "hi": "नमस्ते {name} जी। एक नई योजना आपके काम आ सकती है: {scheme}।",
    "mr": "नमस्कार {name}. एक नवीन योजना तुमच्या उपयोगी पडू शकते: {scheme}.",
    "kn": "ನಮಸ್ಕಾರ {name}. ಹೊಸ ಯೋಜನೆಯೊಂದು ನಿಮಗೆ ಉಪಯುಕ್ತವಾಗಬಹುದು: {scheme}.",
    "te": "నమస్కారం {name}. ఒక కొత్త పథకం మీకు ఉపయోగపడవచ్చు: {scheme}.",
}
_CLOSING = {
    "en": "Would you like us to check if you are eligible? Please visit the branch with your documents.",
    "hi": "क्या आप चाहेंगे कि हम आपकी पात्रता जाँचें? कृपया अपने दस्तावेज़ों के साथ शाखा में आएँ।",
    "mr": "तुमची पात्रता तपासावी असे तुम्हाला वाटते का? कृपया तुमची कागदपत्रे घेऊन शाखेत या.",
    "kn": "ನಿಮ್ಮ ಅರ್ಹತೆಯನ್ನು ಪರಿಶೀಲಿಸಬೇಕೆ? ದಯವಿಟ್ಟು ನಿಮ್ಮ ದಾಖಲೆಗಳೊಂದಿಗೆ ಶಾಖೆಗೆ ಬನ್ನಿ.",
    "te": "మీ అర్హతను తనిఖీ చేయమంటారా? దయచేసి మీ పత్రాలతో శాఖకు రండి.",
}


@lru_cache(maxsize=1)
def load_profiles() -> list[dict]:
    with PROFILES_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)["profiles"]


def reason_english(reason: dict) -> str:
    p = reason.get("params") or {}
    return {
        "asset_gold": f"Has about {p.get('grams')} g of gold",
        "asset_land": f"Owns about {p.get('acres')} acres of land",
        "asset_house": "Owns a house / property",
        "asset_fd": f"Has a fixed deposit of about Rs {p.get('amount'):,}" if p.get("amount") else "Has a fixed deposit",
        "no_collateral": "No collateral needed",
        "occupation": f"Occupation: {p.get('occupation')}",
        "purpose": f"Has mentioned a need for: {p.get('purpose')}",
        "senior": "Senior citizen (60+)",
        "age_ok": "Age within limits",
    }.get(reason["code"], reason["code"])


def suggested_message(scheme: dict, first_name: str, lang: str) -> str:
    name = scheme["name"].get(lang) or scheme["name"]["en"]
    summary = scheme["summary"].get(lang) or scheme["summary"]["en"]
    return f"{_GREETING[lang].format(name=first_name, scheme=name)} {summary} {_CLOSING[lang]}"


def match_customers(scheme: dict) -> list[dict]:
    """Customers (with consent) who meet the scheme's rules for at least one
    of the needs they have mentioned."""
    matches = []
    for profile in load_profiles():
        if not profile.get("offers_consent"):
            continue
        customer = get_customer(profile["customer_id"])
        if not customer:
            continue
        for purpose in profile.get("interests") or ["not_sure"]:
            result = evaluate_scheme(scheme, profile["assets"], profile["occupation"], purpose, customer["age"])
            if result and result["status"] == "likely":
                matches.append({"customer": customer, "purpose": purpose, "reasons": result["reasons"]})
                break
    return matches


def generate_alerts(db: Session, draft: SchemeDraft) -> int:
    """Creates one alert per matching customer. Idempotent: re-running for
    the same scheme never duplicates an alert."""
    scheme = json.loads(draft.draft_json)
    created = 0
    for m in match_customers(scheme):
        c = m["customer"]
        lang = LANGUAGE_CODES.get(c.get("preferred_language"), "en")
        first_name = c["name"].split()[0]
        exists = db.query(SchemeAlert).filter_by(scheme_id=scheme["id"], customer_id=c["customer_id"]).first()
        if exists:
            continue
        db.add(
            SchemeAlert(
                draft_id=draft.id,
                scheme_id=scheme["id"],
                scheme_name=scheme["name"]["en"],
                customer_id=c["customer_id"],
                customer_name=c["name"],
                customer_age=c["age"],
                customer_branch=c.get("branch"),
                language=lang,
                reasons_json=json.dumps([reason_english(r) for r in m["reasons"]]),
                staff_checks_json=json.dumps(scheme.get("staff_checks") or []),
                message_local=suggested_message(scheme, first_name, lang),
                message_english=suggested_message(scheme, first_name, "en"),
            )
        )
        created += 1
    try:
        db.commit()
    except IntegrityError:  # concurrent run created the same alert
        db.rollback()
    if created:
        logger.info("Scheme %s matched %s customer(s)", scheme["id"], created)
    return created


def rescan_all(db: Session) -> int:
    """Re-check every approved scheme — e.g. after customer profiles change."""
    return sum(generate_alerts(db, d) for d in db.query(SchemeDraft).filter(SchemeDraft.status == "approved"))


def serialize_alert(a: SchemeAlert) -> dict:
    return {
        "id": a.id,
        "scheme_id": a.scheme_id,
        "scheme_name": a.scheme_name,
        "customer_id": a.customer_id,
        "customer_name": a.customer_name,
        "customer_age": a.customer_age,
        "customer_branch": a.customer_branch,
        "language": a.language,
        "reasons": json.loads(a.reasons_json or "[]"),
        "staff_checks": json.loads(a.staff_checks_json or "[]"),
        "message_local": a.message_local,
        "message_english": a.message_english,
        "status": a.status,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "handled_by": a.handled_by,
        "handled_at": a.handled_at.isoformat() if a.handled_at else None,
        "note": a.note,
    }


def update_alert(db: Session, alert_id: int, status: str, staff: str, note: str | None) -> SchemeAlert | None:
    a = db.get(SchemeAlert, alert_id)
    if not a:
        return None
    a.status = status
    a.handled_by = staff
    a.handled_at = datetime.utcnow()
    a.note = note
    db.commit()
    return a
