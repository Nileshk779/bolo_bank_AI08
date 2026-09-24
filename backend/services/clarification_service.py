"""
Automatic explanation level ("Simple" / "Normal" / "Detailed").

When the customer (or the employee on their behalf) says they did not
understand, the explanation gets simpler; when they ask to hear more, it
gets more detailed:

    "I don't understand" / "too difficult"   Detailed -> Normal -> Simple
                                              (already Simple: re-explain in
                                              different words with an example)
    "tell me more" / "explain in detail"     Simple -> Normal -> Detailed

A short message like "समजले नाही" refers to the previous answer, so the
previous question is answered again at the new level. A longer message that
also contains a new question ("I don't understand, what is the interest?")
is answered itself at the new level.

Detection is phrase-based across the five supported languages (plus
romanised Hindi/Marathi), so it is instant and predictable — no LLM call.
"""
import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from database.models import Turn

LEVELS = ["simple", "normal", "detailed"]

_SIMPLER = [
    # English
    r"\b(don'?t|do not|didn'?t|did not|can'?t|cannot) (understand|get it|follow)\b", r"\bnot clear\b", r"\bconfus",
    r"\btoo (difficult|hard|complicated|technical)\b", r"\bhard to understand\b", r"\b(simpler|more simply|in simple words|easy words)\b",
    r"\bexplain (it )?again\b", r"\bwhat do you mean\b", r"\bsay (that|it) again\b",
    # Romanised Hindi / Marathi
    r"\bsamaj?h? ?(nahi|nahin|na)\b", r"\bsamj(ha|hi|he) nahi\b", r"\bsamajla nahi\b", r"\bkalla nahi\b",
    r"\b(phir|fir) se (samjhao|samjhaiye|batao|bataiye)\b", r"\b(aasan|asaan|saral|sopya) (bhasha|shabd)",
    # Hindi
    "समझ नहीं", "समझा नहीं", "समझी नहीं", "समझ में नहीं", "समझ नही", "आसान भाषा", "सरल भाषा", "फिर से समझा", "फिर से बता", "बहुत मुश्किल", "कठिन है",
    # Marathi
    "समजले नाही", "समजलं नाही", "समजला नाही", "समजत नाही", "कळले नाही", "कळलं नाही", "कळत नाही", "सोप्या भाषेत", "पुन्हा सांगा", "पुन्हा समजा", "अवघड",
    # Kannada
    "ಅರ್ಥವಾಗಲಿಲ್ಲ", "ಅರ್ಥ ಆಗಲಿಲ್ಲ", "ಅರ್ಥವಾಗುತ್ತಿಲ್ಲ", "ಅರ್ಥ ಆಗ್ತಿಲ್ಲ", "ಸರಳವಾಗಿ", "ಮತ್ತೆ ಹೇಳಿ", "ಮತ್ತೊಮ್ಮೆ ಹೇಳಿ", "ಕಷ್ಟವಾಗಿದೆ",
    # Telugu
    "అర్థం కాలేదు", "అర్థం కావడం లేదు", "అర్థం కావట్లేదు", "సులభంగా", "మళ్లీ చెప్పండి", "మళ్ళీ చెప్పండి", "కష్టంగా ఉంది",
]
_MORE_DETAIL = [
    # English
    r"\btell me more\b", r"\bmore (detail|details|information|info)\b", r"\bin detail\b", r"\bexplain (more|fully|in full)\b",
    r"\belaborate\b", r"\bfull (details|information)\b", r"\bwhat else\b",
    # Romanised Hindi / Marathi
    r"\baur (batao|bataiye|jankari)\b", r"\b(detail|vistar) (me|mein|se)\b", r"\bpuri jankari\b", r"\bajun sanga\b", r"\bsavistar\b",
    # Hindi
    "और बताइए", "और बताओ", "और बताएं", "विस्तार से", "पूरी जानकारी", "ज़्यादा जानकारी", "ज्यादा जानकारी", "अधिक जानकारी", "डिटेल में",
    # Marathi
    "अजून सांगा", "आणखी सांगा", "सविस्तर", "अधिक माहिती", "पूर्ण माहिती", "विस्ताराने",
    # Kannada
    "ಇನ್ನಷ್ಟು ಹೇಳಿ", "ಇನ್ನೂ ಹೇಳಿ", "ವಿವರವಾಗಿ", "ಹೆಚ್ಚಿನ ಮಾಹಿತಿ", "ಪೂರ್ಣ ಮಾಹಿತಿ",
    # Telugu
    "ఇంకా చెప్పండి", "వివరంగా", "మరింత సమాచారం", "పూర్తి వివరాలు", "ఇంకా వివరాలు",
]
_SIMPLER_RE = re.compile("|".join(_SIMPLER), re.IGNORECASE)
_MORE_RE = re.compile("|".join(_MORE_DETAIL), re.IGNORECASE)

# Quick-reply buttons (Yes / No) are not questions to re-explain.
_NOT_QUESTIONS = {"yes", "no", "हाँ", "हां", "नहीं", "हो", "नाही", "ಹೌದು", "ಇಲ್ಲ", "అవును", "కాదు"}

# A message this short is only feedback about the previous answer.
_FEEDBACK_ONLY_MAX_WORDS = 7

FOLLOWUP_INSTRUCTIONS = {
    "simpler": (
        "The customer said they did not understand the previous explanation. Explain the same "
        "thing again more simply, in different words — do not repeat your earlier sentences."
    ),
    "reexplain": (
        "The customer still did not understand, even with a simple explanation. Explain it again "
        "in completely different words, step by step, and use one small everyday example "
        "(for instance from household or village life) to make it clear."
    ),
    "more_detail": (
        "The customer asked for more detail. Give a fuller explanation: include the steps, the "
        "conditions and any numbers that appear in the policy context — but nothing beyond it."
    ),
}


def detect_feedback(text: str) -> str | None:
    """'simpler', 'more_detail' or None."""
    text = text or ""
    if _SIMPLER_RE.search(text):
        return "simpler"
    if _MORE_RE.search(text):
        return "more_detail"
    return None


def next_level(current: str, direction: str) -> tuple[str, str]:
    """Returns (new_level, change) where change is 'simpler', 'reexplain' or 'more_detail'."""
    i = LEVELS.index(current) if current in LEVELS else 0
    if direction == "simpler":
        return (LEVELS[i - 1], "simpler") if i > 0 else ("simple", "reexplain")
    return LEVELS[min(i + 1, len(LEVELS) - 1)], "more_detail"


def is_feedback_only(text: str) -> bool:
    return len((text or "").split()) <= _FEEDBACK_ONLY_MAX_WORDS


@dataclass
class Plan:
    query: str  # what to actually answer
    complexity: str  # level to answer at
    level_change: str | None = None  # 'simpler' | 'reexplain' | 'more_detail'
    reexplained_question: str | None = None  # set when re-answering the previous question
    instruction: str | None = None  # extra instruction for the LLM


def plan(text: str, complexity: str, previous_question: str | None) -> Plan:
    direction = detect_feedback(text)
    if not direction:
        return Plan(query=text, complexity=complexity)
    level, change = next_level(complexity, direction)
    instruction = FOLLOWUP_INSTRUCTIONS[change]
    if is_feedback_only(text) and previous_question:
        return Plan(query=previous_question, complexity=level, level_change=change, reexplained_question=previous_question, instruction=instruction)
    return Plan(query=text, complexity=level, level_change=change, instruction=instruction)


def last_customer_question(db: Session, session_id: str) -> str | None:
    """Most recent real question the customer asked in this session (skips
    feedback like "I don't understand" and non-question log lines)."""
    turns = (
        db.query(Turn)
        .filter(Turn.session_id == session_id, Turn.role == "customer")
        .order_by(Turn.id.desc())
        .limit(20)
        .all()
    )
    for t in turns:
        text = (t.text_local or "").strip()
        if not text or text.startswith("Loan eligibility check") or text.lower().strip(" .!?") in _NOT_QUESTIONS:
            continue
        if detect_feedback(text) and is_feedback_only(text):
            continue
        return text
    return None
