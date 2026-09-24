"""
Risk analysis — lightweight, rule-based classification of whether a query
touches something where an AI answer should visibly defer to a human
employee, rather than an ML classifier or a redesign of the security model.

This app has no ability to execute banking actions today — no transfers, no
PIN/OTP changes, nothing irreversible. "Risk analysis" here means: does this
query touch money movement, account security, or a dispute, such that the
response should be framed as "a staff member needs to handle this" instead
of sounding fully self-service? This governs response *framing* only. It
does not (and, given the app has no action-execution capability, could not)
grant or block any actual action — the human-in-the-loop guarantee comes
from the AI never having execution capability in the first place, not from
this classifier being airtight.

Keyword-based and intentionally simple: easy to audit, easy to extend, and
proportionate to a hackathon MVP where the guarantee that matters (no
AI-executed actions) doesn't depend on perfect classification here.
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class RiskAssessment:
    level: str  # "low" | "medium" | "high"
    flags: list[str] = field(default_factory=list)
    requires_human_review: bool = False
    note: str = ""


# term -> human-readable flag label. High-risk: security/money-movement
# terms where a wrong or overconfident AI answer matters most.
_HIGH_RISK_TERMS = {
    "transfer": "funds transfer",
    "send money": "funds transfer",
    "wire": "funds transfer",
    "otp": "one-time password / authentication",
    "pin": "PIN / authentication",
    "cvv": "card security code",
    "password": "credentials",
    "close my account": "account closure",
    "close account": "account closure",
    "dispute": "transaction dispute",
    "fraud": "fraud report",
    "unauthorized": "fraud report",
    "block my card": "card security",
    "lost card": "card security",
    "stolen": "fraud / theft report",
}

# Medium-risk: still worth a human glance, but not urgent/security-critical.
_MEDIUM_RISK_TERMS = {
    "loan": "loan application",
    "large withdrawal": "large cash transaction",
    "change my address": "KYC / personal detail change",
    "update my details": "KYC / personal detail change",
    "nominee": "nominee change",
}

HIGH_RISK_NOTE = (
    "This request touches account security or money movement — a staff member "
    "must verify the customer's identity and handle it directly; the AI cannot "
    "and does not act on this."
)
MEDIUM_RISK_NOTE = "This request may need staff review before proceeding."


def assess(text: str) -> RiskAssessment:
    lowered = text.lower()

    high_flags = sorted({label for term, label in _HIGH_RISK_TERMS.items() if term in lowered})
    if high_flags:
        return RiskAssessment(level="high", flags=high_flags, requires_human_review=True, note=HIGH_RISK_NOTE)

    medium_flags = sorted({label for term, label in _MEDIUM_RISK_TERMS.items() if term in lowered})
    if medium_flags:
        return RiskAssessment(level="medium", flags=medium_flags, requires_human_review=True, note=MEDIUM_RISK_NOTE)

    return RiskAssessment(level="low", flags=[], requires_human_review=False, note="")
