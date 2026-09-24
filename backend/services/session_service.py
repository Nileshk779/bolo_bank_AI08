"""
Session/audit-log business logic: turn logging (the audit trail) and
session summary generation.

Summary generation replaces the original MVP's naive approach (just joining
every assistant reply into one paragraph) with a structured, employee-
oriented summary — customer issue, important facts, relevant policy,
recommended next action, and what's still unresolved — so an employee can
understand a customer's situation without asking them to repeat it. This
goes through the LLM (via llm_service.chat_completion), then every text
field is passed through the Response Privacy Layer's redact_sensitive_values()
as a defense-in-depth pass: the prompt instructs the model not to include
real account numbers/balances/OTPs/PINs/card numbers, but since a customer
could say one out loud during the conversation (and their turn may contain sensitive values), this catches anything that slips through into the summary
specifically. Raw turn-by-turn audit text is also redacted before storage to minimize retained sensitive data.
"""
import json
import logging
import uuid

from sqlalchemy.orm import Session

from database.models import Turn
from services.llm_service import LANGUAGE_NAMES, chat_completion
from services.response_privacy_service import redact_sensitive_values

logger = logging.getLogger("bolobank.session")


def new_session_id() -> str:
    return str(uuid.uuid4())[:8]


def log_turn(db: Session, session_id: str, role: str, language: str, text_local: str, text_english: str) -> None:
    db.add(
        Turn(
            session_id=session_id,
            role=role,
            language=language,
            text_local=redact_sensitive_values(text_local or "").safe_text,
            text_english=redact_sensitive_values(text_english or "").safe_text,
        )
    )
    db.commit()


def _clean(text: str) -> str:
    return redact_sensitive_values(text or "").safe_text


def _empty_summary(language: str) -> dict:
    return {
        "language": LANGUAGE_NAMES.get(language, language),
        "customer_issue": "No interaction recorded in this session.",
        "important_information": [],
        "relevant_policy": "",
        "recommended_next_action": "",
        "unresolved": "",
    }


def generate_structured_summary(turns: list[dict], language: str) -> dict:
    """One LLM call over the full transcript, producing the structured
    fields an employee actually needs — not a decorative rewording of the
    transcript, but an extraction of what mattered."""
    if not turns:
        return _empty_summary(language)

    transcript = "\n".join(
        f"{t['role'].upper()}: {t['text_local']}" + (f" (EN: {t['text_english']})" if t.get("text_english") else "")
        for t in turns
    )

    system_prompt = (
        "You are summarizing a bank branch customer voice interaction for the employee's "
        "records, so the employee can understand the customer's situation without asking "
        "them to repeat everything. You are given the full transcript below.\n\n"
        "IMPORTANT: do not include any real account numbers, balances, OTPs, PINs, CVVs, or "
        "card numbers in the summary, even if they appear in the transcript — refer to such "
        "things only generically (e.g. 'discussed account balance') if it's relevant context.\n\n"
        f"Transcript:\n{transcript}\n\n"
        "Respond with ONLY a JSON object (no markdown fences, no extra text) with exactly "
        "these keys:\n"
        '  "customer_issue": one short sentence describing what the customer needed help with.\n'
        '  "important_information": a JSON array of short strings — specific facts the '
        'employee should know (e.g. "Last payment received in May.", "Customer has '
        'passbook."). Empty array if there is nothing notable.\n'
        '  "relevant_policy": one short sentence naming the relevant bank policy or process '
        "that applies, or an empty string if none clearly applies.\n"
        '  "recommended_next_action": one short, concrete next step for the employee to take.\n'
        '  "unresolved": one short sentence describing what still needs to be resolved or '
        "verified, or an empty string if the interaction was fully resolved."
    )

    raw = chat_completion(system_prompt, transcript, max_tokens=400, json_mode=True)

    try:
        parsed = json.loads(raw or "{}")
    except json.JSONDecodeError:
        logger.warning("Session summary LLM response was not valid JSON, falling back to empty fields")
        parsed = {}

    important_info = [_clean(item) for item in (parsed.get("important_information") or []) if item]

    return {
        "language": LANGUAGE_NAMES.get(language, language),
        "customer_issue": _clean(parsed.get("customer_issue") or ""),
        "important_information": important_info,
        "relevant_policy": _clean(parsed.get("relevant_policy") or ""),
        "recommended_next_action": _clean(parsed.get("recommended_next_action") or ""),
        "unresolved": _clean(parsed.get("unresolved") or ""),
    }


def get_session_summary(db: Session, session_id: str) -> dict:
    turns = db.query(Turn).filter(Turn.session_id == session_id).order_by(Turn.created_at).all()

    turn_list = [
        {
            "role": t.role,
            "language": t.language,
            "text_local": t.text_local,
            "text_english": t.text_english,
            "created_at": t.created_at.isoformat(),
        }
        for t in turns
    ]

    language = turns[0].language if turns else "en"
    summary = generate_structured_summary(turn_list, language)

    return {"session_id": session_id, "turns": turn_list, **summary}
