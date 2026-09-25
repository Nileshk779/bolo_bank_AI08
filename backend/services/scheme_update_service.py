"""
Daily scheme updates, with a human approval step.

    announcement feed ──► extract (LLM, or demo preset) ──► validate
            │                                                  │
            ▼                                                  ▼
     SchemeDraft "pending"  ──►  employee reviews / edits  ──►  approved
                                                               │
                                          eligibility checker uses it
                                          (merged with loan_schemes.json)

Nothing the AI extracts reaches customers until an authorized employee
approves it, and a draft with validation issues cannot be approved until
they are fixed. Every run is recorded in SchemeUpdateRun so staff can see
when the catalogue was last checked.

The feed here is a local JSON file of SIMULATED announcements
(data/scheme_feed.json). In production, replace LocalJsonFeed with a
connector to official sources (RBI notifications, the bank's product team,
government scheme portals) that returns the same item shape.
"""
import json
import logging
import re
from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session

from core.config import settings
from database.models import SchemeDraft, SchemeUpdateRun
from services.data_service import DATA_DIR
from services.eligibility_service import ASSET_TYPES, OCCUPATIONS, PURPOSES, load_catalogue

logger = logging.getLogger("bolobank.scheme_updates")

FEED_PATH = DATA_DIR / "scheme_feed.json"
LANGUAGES = ("en", "hi", "mr", "kn", "te")
KINDS = ("bank_product", "government_scheme")
PURPOSE_RULES = tuple(p for p in PURPOSES if p != "not_sure")


def known_documents() -> set[str]:
    """Document codes the customer UI can display (it has translations for
    exactly the codes used in the base catalogue)."""
    return {d for s in load_catalogue()["schemes"] for d in s["documents"]}


# --------------------------------------------------------------- feed --- #
class LocalJsonFeed:
    """Demo source. Only returns items published on or before `today`, so
    items dated in the future appear on the day they are "published"."""

    def fetch(self, today: date) -> list[dict]:
        with FEED_PATH.open("r", encoding="utf-8") as f:
            items = json.load(f)["items"]
        return [i for i in items if date.fromisoformat(i["published_on"]) <= today]


# ---------------------------------------------------------- extraction --- #
_EXTRACTION_PROMPT = f"""You convert a bank or government loan announcement into a structured record for a
loan-eligibility checker used by elderly, low-literacy customers in India.

Return ONLY a JSON object with exactly these keys:
- "id": short snake_case identifier
- "kind": one of {list(KINDS)}
- "name": object with keys {list(LANGUAGES)} — short scheme name in each language
- "summary": object with keys {list(LANGUAGES)} — one or two simple sentences in each language,
  plain words, no jargon; do not add facts that are not in the announcement
- "rules": object with
    "collateral_any": list from {list(ASSET_TYPES)} (empty list if no security is needed),
    "occupations": list from {list(OCCUPATIONS)} or null if anyone can apply,
    "purposes": list from {list(PURPOSE_RULES)} or null if any purpose,
    "min_age": integer or null, "max_age": integer or null
- "estimate": null
- "documents": list of codes chosen from: {{documents}}
- "valid_until": ISO date (YYYY-MM-DD) if the announcement gives an end date, else null
- "staff_checks": list of short English sentences for conditions the fields above cannot
  express (for example gender, group membership, income limits, state-specific rules);
  empty list if none

Use only the allowed values. If the announcement needs something outside them, use the
closest allowed value; a human employee will review every record before it is used."""


def _extract_with_llm(item: dict) -> dict:
    from services.llm_service import chat_completion

    prompt = _EXTRACTION_PROMPT.replace("{documents}", ", ".join(sorted(known_documents())))
    raw = chat_completion(prompt, f"Title: {item['title']}\n\n{item['raw_text']}", max_tokens=1500, json_mode=True)
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        raise ValueError("LLM returned no JSON object")
    return json.loads(match.group(0))


def extract(item: dict) -> tuple[dict, str]:
    """Returns (draft, method)."""
    if settings.SCHEME_EXTRACTION_MODE == "llm" and settings.GROQ_API_KEY:
        try:
            return _extract_with_llm(item), "llm"
        except Exception as exc:  # network, quota, bad JSON — fall back, never crash the job
            logger.warning("LLM extraction failed for %s: %s", item["feed_id"], exc)
            return dict(item["demo_extraction"]), "preset_after_llm_error"
    return dict(item["demo_extraction"]), "preset"


# ---------------------------------------------------------- validation --- #
def validate(draft: dict, existing_ids: set[str]) -> list[str]:
    """Human-readable problems that block approval. Empty list = OK."""
    try:
        return _validate(draft, existing_ids)
    except Exception as exc:  # malformed LLM output (wrong types etc.)
        return [f"Draft is malformed and could not be checked: {exc}"]


def _validate(draft: dict, existing_ids: set[str]) -> list[str]:
    issues: list[str] = []
    if not re.fullmatch(r"[a-z0-9_]{3,60}", str(draft.get("id", ""))):
        issues.append("Scheme id must be 3–60 lowercase letters, digits or underscores.")
    elif draft["id"] in existing_ids:
        issues.append(f"A scheme with id '{draft['id']}' already exists.")
    if draft.get("kind") not in KINDS:
        issues.append(f"Kind must be one of: {', '.join(KINDS)}.")
    for field in ("name", "summary"):
        values = draft.get(field) or {}
        missing = [lang for lang in LANGUAGES if not str(values.get(lang, "")).strip()]
        if missing:
            issues.append(f"{field.capitalize()} is missing for: {', '.join(missing)}.")

    rules = draft.get("rules") or {}
    bad = [a for a in rules.get("collateral_any") or [] if a not in ASSET_TYPES]
    if bad:
        issues.append(f"Unknown collateral type(s): {', '.join(bad)}.")
    if rules.get("occupations") is not None:
        bad = [o for o in rules["occupations"] if o not in OCCUPATIONS]
        if bad:
            issues.append(f"Unknown occupation(s): {', '.join(bad)} — choose from the allowed list.")
        if not rules["occupations"]:
            issues.append("Occupations list is empty — select at least one, or allow anyone.")
    if rules.get("purposes") is not None:
        bad = [p for p in rules["purposes"] if p not in PURPOSE_RULES]
        if bad:
            issues.append(f"Unknown purpose(s): {', '.join(bad)}.")
        if not rules["purposes"]:
            issues.append("Purposes list is empty — select at least one, or allow any purpose.")
    min_age, max_age = rules.get("min_age"), rules.get("max_age")
    for label, value in (("Minimum age", min_age), ("Maximum age", max_age)):
        if value is not None and not (isinstance(value, int) and 18 <= value <= 110):
            issues.append(f"{label} must be a whole number between 18 and 110.")
    if isinstance(min_age, int) and isinstance(max_age, int) and min_age > max_age:
        issues.append("Minimum age is greater than maximum age.")

    est = draft.get("estimate")
    if est is not None:
        if est.get("method") not in ("gold_value", "fd_value") or not (0 < float(est.get("ratio", 0)) <= 0.95):
            issues.append("Estimate must use gold_value or fd_value with a ratio between 0 and 0.95.")
        elif {"gold_value": "gold", "fd_value": "fd"}[est["method"]] not in (rules.get("collateral_any") or []):
            issues.append("Estimate method does not match the collateral type.")

    docs = draft.get("documents") or []
    if not docs:
        issues.append("At least one document is required.")
    bad = [d for d in docs if d not in known_documents()]
    if bad:
        issues.append(f"Unknown document(s): {', '.join(bad)} — the customer screen has no translation for them.")

    checks = draft.get("staff_checks") or []
    if not isinstance(checks, list) or not all(isinstance(c, str) and 0 < len(c) <= 200 for c in checks) or len(checks) > 6:
        issues.append("Staff checks must be up to 6 short sentences.")

    if draft.get("valid_until"):
        try:
            date.fromisoformat(draft["valid_until"])
        except ValueError:
            issues.append("Valid-until must be a date in YYYY-MM-DD format.")
    return issues


# ------------------------------------------------------------ job & db --- #
def _existing_ids(db: Session, exclude_draft_id: int | None = None) -> set[str]:
    ids = {s["id"] for s in load_catalogue()["schemes"]}
    q = db.query(SchemeDraft).filter(SchemeDraft.status == "approved")
    if exclude_draft_id is not None:
        q = q.filter(SchemeDraft.id != exclude_draft_id)
    ids |= {json.loads(d.draft_json).get("id") for d in q}
    return ids


def run_update(db: Session, trigger: str = "manual", today: date | None = None, feed=None) -> SchemeUpdateRun:
    today = today or date.today()
    feed = feed or LocalJsonFeed()
    run = SchemeUpdateRun(trigger=trigger)
    db.add(run)
    db.commit()
    try:
        items = feed.fetch(today)
        seen = {feed_id for (feed_id,) in db.query(SchemeDraft.feed_id)}
        new = 0
        for item in items:
            if item["feed_id"] in seen:
                continue
            draft, method = extract(item)
            issues = validate(draft, _existing_ids(db))
            db.add(
                SchemeDraft(
                    feed_id=item["feed_id"],
                    title=item["title"],
                    source_name=item["source_name"],
                    source_url=item.get("source_url"),
                    published_on=item["published_on"],
                    raw_text=item["raw_text"],
                    draft_json=json.dumps(draft, ensure_ascii=False),
                    extraction_method=method,
                    validation_issues=json.dumps(issues),
                    status="pending",
                )
            )
            new += 1
        run.items_seen = len(items)
        run.new_drafts = new
    except Exception as exc:
        logger.exception("Scheme update run failed")
        run.error = str(exc)
    run.finished_at = datetime.utcnow()
    db.commit()
    return run


def serialize_draft(d: SchemeDraft) -> dict[str, Any]:
    return {
        "id": d.id,
        "feed_id": d.feed_id,
        "title": d.title,
        "source_name": d.source_name,
        "source_url": d.source_url,
        "published_on": d.published_on,
        "raw_text": d.raw_text,
        "draft": json.loads(d.draft_json),
        "extraction_method": d.extraction_method,
        "validation_issues": json.loads(d.validation_issues or "[]"),
        "status": d.status,
        "fetched_at": d.fetched_at.isoformat() if d.fetched_at else None,
        "reviewed_by": d.reviewed_by,
        "reviewed_at": d.reviewed_at.isoformat() if d.reviewed_at else None,
        "review_note": d.review_note,
    }


def serialize_run(r: SchemeUpdateRun | None) -> dict | None:
    if not r:
        return None
    return {
        "trigger": r.trigger,
        "started_at": r.started_at.isoformat() if r.started_at else None,
        "finished_at": r.finished_at.isoformat() if r.finished_at else None,
        "items_seen": r.items_seen,
        "new_drafts": r.new_drafts,
        "error": r.error,
    }


def apply_edits(draft: dict, edits: dict) -> dict:
    """Staff can correct the English text, the rules and the documents.
    Regional-language text is not edited here (it would need a native
    speaker); if the English name changes, staff should re-check it."""
    updated = json.loads(json.dumps(draft))
    if "name_en" in edits:
        updated.setdefault("name", {})["en"] = edits["name_en"]
    if "summary_en" in edits:
        updated.setdefault("summary", {})["en"] = edits["summary_en"]
    if "rules" in edits:
        updated["rules"] = {**(updated.get("rules") or {}), **edits["rules"]}
    if "documents" in edits:
        updated["documents"] = edits["documents"]
    if "valid_until" in edits:
        updated["valid_until"] = edits["valid_until"] or None
    if "kind" in edits:
        updated["kind"] = edits["kind"]
    if "staff_checks" in edits:
        updated["staff_checks"] = [c.strip() for c in edits["staff_checks"] if c and c.strip()]
    return updated


class ReviewError(Exception):
    def __init__(self, message: str, issues: list[str] | None = None):
        super().__init__(message)
        self.issues = issues or []


def save_edits(db: Session, draft_id: int, edits: dict) -> SchemeDraft:
    d = _pending(db, draft_id)
    updated = apply_edits(json.loads(d.draft_json), edits)
    d.draft_json = json.dumps(updated, ensure_ascii=False)
    d.validation_issues = json.dumps(validate(updated, _existing_ids(db)))
    db.commit()
    return d


def approve(db: Session, draft_id: int, staff: str, note: str | None = None) -> SchemeDraft:
    d = _pending(db, draft_id)
    issues = validate(json.loads(d.draft_json), _existing_ids(db, exclude_draft_id=d.id))
    if issues:
        d.validation_issues = json.dumps(issues)
        db.commit()
        raise ReviewError("Fix the validation issues before approving.", issues)
    d.status = "approved"
    d.reviewed_by = staff
    d.reviewed_at = datetime.utcnow()
    d.review_note = note
    d.validation_issues = "[]"
    db.commit()
    # Import here: scheme_alert_service imports this module's models too.
    from services.scheme_alert_service import generate_alerts

    generate_alerts(db, d)
    return d


def reject(db: Session, draft_id: int, staff: str, note: str | None = None) -> SchemeDraft:
    d = _pending(db, draft_id)
    d.status = "rejected"
    d.reviewed_by = staff
    d.reviewed_at = datetime.utcnow()
    d.review_note = note
    db.commit()
    return d


def _pending(db: Session, draft_id: int) -> SchemeDraft:
    d = db.get(SchemeDraft, draft_id)
    if not d:
        raise ReviewError("Draft not found")
    if d.status != "pending":
        raise ReviewError(f"Draft is already {d.status}")
    return d


def get_approved_schemes(db: Session, today: date | None = None) -> list[dict]:
    """Approved, unexpired schemes in loan_schemes.json shape, marked as new
    so the customer screen can highlight them."""
    today = today or date.today()
    schemes = []
    for d in db.query(SchemeDraft).filter(SchemeDraft.status == "approved").order_by(SchemeDraft.reviewed_at.desc()):
        s = json.loads(d.draft_json)
        if s.get("valid_until") and date.fromisoformat(s["valid_until"]) < today:
            continue
        s["source"] = {"name": d.source_name, "url": d.source_url}
        s["added_on"] = d.reviewed_at.date().isoformat() if d.reviewed_at else None
        schemes.append(s)
    return schemes


def run_scheduled_update() -> None:
    """One scheduled round. However many processes call this (API servers
    with SCHEME_AUTO_UPDATE, or worker.py), only the one that claims the
    database lock runs it; the lock lasts (almost) one interval."""
    from database.session import SessionLocal
    from services import job_lock

    db = SessionLocal()
    try:
        ttl = max(60.0, settings.SCHEME_UPDATE_INTERVAL_HOURS * 3600 - 60)
        if not job_lock.acquire(db, "scheme_update", ttl):
            logger.info("Scheme update: another process is handling this round")
            return
        run = run_update(db, trigger="scheduled")
        logger.info("Scheme update: %s items seen, %s new drafts for staff review", run.items_seen, run.new_drafts)
    finally:
        db.close()


if __name__ == "__main__":
    # One-off run for an external scheduler (cron, Windows Task Scheduler,
    # a Kubernetes CronJob):  python -m services.scheme_update_service
    from database.session import SessionLocal

    session = SessionLocal()
    try:
        result = run_update(session, trigger="scheduled")
        print(f"Scheme update: {result.items_seen} items seen, {result.new_drafts} new drafts, error={result.error}")
    finally:
        session.close()
