"""
Reusable Response Privacy Layer.

CRITICAL PRODUCT REQUIREMENT: sensitive financial information must never be
spoken aloud by TTS in a public banking environment, even though it's fine
to show it on the customer's authenticated screen. This module is the
single mechanism behind that guarantee — any current or future feature that
produces a response passes through here, rather than each feature
reimplementing its own redaction.

Two complementary layers, used together:

1. STRUCTURED (the primary path): a caller that already knows it's
   returning a specific sensitive value (see account_service.py) never puts
   that value into prose text at all. It builds a `spoken_response` (a safe,
   generic phrase) and a separate `visual_data` payload for the screen. The
   raw value exists in exactly one place — visual_data — and is never
   constructed as part of any string that could reach TTS.

2. UNSTRUCTURED / DEFENSE-IN-DEPTH: `protect_for_speech()` regex-scans any
   free-form text (e.g. an LLM's grounded policy answer, which shouldn't
   normally contain personal financial data since it's only grounded in
   static policy documents, but might if the model misbehaves) and replaces
   anything that looks like sensitive personal data with a safe phrase.
   This runs on every orchestrator response before it's returned, AND
   unconditionally at the single TTS choke point (POST /api/speak) as a
   last line of defense — regardless of what any caller claims about text
   already being safe.

Because #1 never lets the value touch prose, and #2 is a broad net over
whatever prose does exist, a future feature (transaction history,
statements, card management, ...) automatically gets this protection by
routing its output through these same two functions — no per-feature
privacy logic to remember to write.
"""
import re
from dataclasses import dataclass

# Shown instead of speaking a value that exists as structured visual_data
# (balance, account number, transaction details, card number, ...).
SCREEN_ONLY_PHRASE = {
    "en": "This information is displayed securely on your screen.",
    "hi": "यह जानकारी आपकी स्क्रीन पर सुरक्षित रूप से दिखाई गई है।",
    "mr": "ही माहिती तुमच्या स्क्रीनवर सुरक्षितपणे दाखवली आहे.",
    "te": "ఈ సమాచారం మీ స్క్రీన్‌పై సురక్షితంగా చూపబడింది.",
    "kn": "ಈ ಮಾಹಿತಿಯನ್ನು ನಿಮ್ಮ ಪರದೆಯ ಮೇಲೆ ಸುರಕ್ಷಿತವಾಗಿ ತೋರಿಸಲಾಗಿದೆ.",
}

# Shown for values that can never be looked up or displayed at all — OTP,
# PIN, CVV, Aadhaar/PAN. Unlike balance/account number, these aren't a
# "show on screen instead" case: there is no value to show, by design.
CANNOT_DISCLOSE_PHRASE = {
    "en": (
        "For your security, this can't be displayed or read aloud by the assistant. "
        "Please ask a branch staff member for help with this."
    ),
    "hi": (
        "आपकी सुरक्षा के लिए, यह जानकारी सहायक द्वारा नहीं दिखाई या बोली जा सकती। "
        "कृपया शाखा कर्मचारी से सहायता लें।"
    ),
    "mr": (
        "तुमच्या सुरक्षिततेसाठी, ही माहिती सहाय्यकाद्वारे दाखवली किंवा बोलली जाऊ शकत नाही. "
        "कृपया शाखा कर्मचाऱ्यांची मदत घ्या."
    ),
    "te": (
        "మీ భద్రత కోసం, ఈ సమాచారాన్ని సహాయకుడు చూపించలేరు లేదా చెప్పలేరు. "
        "దయచేసి బ్రాంచ్ సిబ్బంది సహాయం తీసుకోండి."
    ),
    "kn": (
        "ನಿಮ್ಮ ಭದ್ರತೆಗಾಗಿ, ಈ ಮಾಹಿತಿಯನ್ನು ಸಹಾಯಕರು ತೋರಿಸಲು ಅಥವಾ ಹೇಳಲು ಸಾಧ್ಯವಿಲ್ಲ. "
        "ದಯವಿಟ್ಟು ಶಾಖೆಯ ಸಿಬ್ಬಂದಿಯ ಸಹಾಯ ಪಡೆಯಿರಿ."
    ),
}


def screen_only_phrase(language: str) -> str:
    return SCREEN_ONLY_PHRASE.get(language, SCREEN_ONLY_PHRASE["en"])


def cannot_disclose_phrase(language: str) -> str:
    return CANNOT_DISCLOSE_PHRASE.get(language, CANNOT_DISCLOSE_PHRASE["en"])


# --- Defense-in-depth: regex-based detection over free-form prose ---------

# Keyword windows: a personal-possessive sensitive keyword followed (within
# ~40 chars) by a number is masked as a unit — "your balance is Rs. 42,350",
# "OTP is 4821", "PIN 1234", "CVV: 302", card/account numbers, etc.
#
# Deliberately narrow for "balance": only possessive/personal phrasing
# ("your balance", "current balance", "available balance", "account
# balance") triggers redaction. Generic policy phrasing like "minimum
# balance requirement is Rs. 1,000" is not an individual customer's data
# and must stay speakable — bank policy answers depend on being able to
# state these figures aloud.
_SENSITIVE_KEYWORDS = (
    r"your balance|current balance|available balance|account balance|"
    r"account number|acc(?:ount)? no\.?|a/?c no\.?|otp|one[- ]time password|"
    r"\bpin\b|cvv|card number|debit card number|credit card number|"
    r"passbook number|aadhaar|aadhar|pan number|pan card number|"
    r"transaction amount|amount debited|amount credited"
)

_KEYWORD_THEN_NUMBER = re.compile(
    rf"(?i)\b(?:{_SENSITIVE_KEYWORDS})\b[^.\n]{{0,40}}?"
    r"(₹\s?[\d,]+(?:\.\d+)?|rs\.?\s?[\d,]+(?:\.\d+)?|inr\s?[\d,]+(?:\.\d+)?|\d[\d,]{2,})"
)

# 3-6 digit runs immediately followed by an OTP/PIN/CVV-type keyword, in
# case the number comes first: "4821 is your OTP".
_NUMBER_THEN_KEYWORD = re.compile(rf"(?i)\b(\d{{3,6}})\b[^.\n]{{0,15}}?\b(?:{_SENSITIVE_KEYWORDS})\b")

# Long digit runs that look like account/card numbers on their own (8+
# consecutive digits, allowing spaces/hyphens every few digits).
_LONG_NUMBER = re.compile(r"\b(?:\d[\s-]?){8,19}\d\b")


@dataclass(frozen=True)
class ProtectedText:
    safe_text: str
    redacted: bool


def _redact(text: str, replacement: str) -> ProtectedText:
    """Shared low-level pass: applies every detection pattern, replacing
    matches with `replacement`. Used by both protect_for_speech() (replaces
    with a spoken "shown on screen" phrase) and redact_sensitive_values()
    (replaces with a generic placeholder, for non-speech contexts like
    session summaries or logs)."""
    if not text or not text.strip():
        return ProtectedText(safe_text=text, redacted=False)

    redacted = False
    safe_text = text
    for pattern in (_KEYWORD_THEN_NUMBER, _NUMBER_THEN_KEYWORD, _LONG_NUMBER):
        new_text, count = pattern.subn(replacement, safe_text)
        if count:
            redacted = True
            safe_text = new_text
    return ProtectedText(safe_text=safe_text, redacted=redacted)


def protect_for_speech(text: str, language: str = "en") -> ProtectedText:
    """Regex-scans free-form text and masks anything that looks like
    personal financial data, replacing it with SCREEN_ONLY_PHRASE. Never
    mutates the original — callers keep that for on-screen display. Use
    this specifically for text that's about to be sent to TTS."""
    return _redact(text, screen_only_phrase(language))


def redact_sensitive_values(text: str) -> ProtectedText:
    """Same detection, but for non-speech contexts (e.g. an AI-generated
    session summary shown to an employee, or anything else that isn't
    headed to TTS) — replaces matches with a generic placeholder instead of
    a spoken phrase, since "shown on screen" doesn't make sense in a
    written summary that's already on screen."""
    return _redact(text, "[sensitive information omitted]")
