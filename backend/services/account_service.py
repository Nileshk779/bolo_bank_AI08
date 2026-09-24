"""
DEMO / MOCK customer account data.

BoloBank's AI Orchestrator answers policy questions by retrieving from a
static knowledge base (see rag_service.py) — it has no connection to a real
core banking system and cannot look up a real customer's actual balance,
transactions, or card details. This module provides a small, clearly-fake
demo account so the privacy-aware voice disclosure feature (see
response_privacy_service.py) has something concrete to demonstrate and test
end-to-end: "what is my balance" needs an actual value to withhold from
speech and show on screen instead.

Replace get_demo_account() with a real, per-customer core-banking lookup
before any real deployment. Nothing else — the intent detection below, the
orchestrator, or the privacy layer — needs to change when that happens;
they only depend on this function's return shape.
"""
import re
from dataclasses import dataclass

# --- Demo data -------------------------------------------------------- #


@dataclass(frozen=True)
class DemoAccount:
    account_number: str
    balance: str
    currency: str
    last_transaction_description: str
    last_transaction_amount: str
    last_transaction_date: str
    card_number_masked: str


def get_demo_account() -> DemoAccount:
    return DemoAccount(
        account_number="1234567890123",
        balance="12450",
        currency="INR",
        last_transaction_description="Debit — Grocery Store",
        last_transaction_amount="850",
        last_transaction_date="2026-08-19",
        card_number_masked="**** **** **** 4821",
    )


def build_visual_data(intent: str, account: DemoAccount) -> dict:
    """Structured, screen-only payload for a given account-data intent.
    This is the ONLY place the actual value appears — it is never
    interpolated into prose text that could reach TTS."""
    if intent == "balance":
        return {"type": "balance", "label": "Current Available Balance", "value": account.balance, "currency": account.currency}
    if intent == "account_number":
        masked = "•" * max(0, len(account.account_number) - 4) + account.account_number[-4:]
        return {"type": "account_number", "label": "Account Number", "value": masked}
    if intent == "transaction":
        return {
            "type": "transaction",
            "label": "Latest Transaction",
            "value": {
                "description": account.last_transaction_description,
                "amount": account.last_transaction_amount,
                "currency": account.currency,
                "date": account.last_transaction_date,
            },
        }
    if intent == "card_number":
        return {"type": "card_number", "label": "Card Number", "value": account.card_number_masked}
    raise ValueError(f"No visual_data builder for intent={intent!r}")


# --- Intent detection --------------------------------------------------- #

# Intents where a value CAN be shown on screen (just never spoken).
DISPLAYABLE_INTENTS = ("balance", "account_number", "transaction", "card_number")
# Intents where there is no value to show at all — these are never
# retrievable/displayable by design (OTP is transaction-time-only, PIN/CVV/
# ID numbers are never stored or surfaced by the assistant).
NEVER_DISCLOSE_INTENTS = ("otp", "pin", "cvv", "id_number")

_INTENT_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("otp", re.compile(r"(?i)\botp\b|one[- ]time password")),
    ("pin", re.compile(r"(?i)\bpin\b|\bmpin\b")),
    ("cvv", re.compile(r"(?i)\bcvv\b")),
    ("id_number", re.compile(r"(?i)\baadhaar\b|\baadhar\b|\bpan\s*(card)?\s*number\b|\bpan\s*card\b")),
    ("card_number", re.compile(r"(?i)\bcard\s*number\b|\bdebit\s*card\b.*\bnumber\b|\bcredit\s*card\b.*\bnumber\b")),
    ("transaction", re.compile(r"(?i)\b(last|recent|latest)\s+transaction\b|\btransaction\s+history\b")),
    ("account_number", re.compile(r"(?i)\baccount\s*number\b|\bacc(?:ount)?\.?\s*no\.?\b|\ba/?c\s*no\.?\b")),
    ("balance", re.compile(r"(?i)\bbalance\b|\bhow much money\b|\bhow much do i have\b")),
]


def detect_account_intent(text: str) -> str | None:
    """Returns one of DISPLAYABLE_INTENTS / NEVER_DISCLOSE_INTENTS, or None
    if the query isn't asking for a specific piece of the customer's own
    account data (i.e. it's a general policy question that should go
    through normal RAG/LLM retrieval instead).

    Order matters: more specific/sensitive intents (otp/pin/cvv/id_number)
    are checked before the broader "balance"/"account number" patterns, so
    e.g. "what is my card's CVV number" matches cvv, not account_number.
    """
    for intent, pattern in _INTENT_PATTERNS:
        if pattern.search(text):
            return intent
    return None
