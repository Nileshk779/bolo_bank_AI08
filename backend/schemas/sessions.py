from pydantic import BaseModel


class TurnOut(BaseModel):
    role: str
    language: str
    text_local: str
    text_english: str
    created_at: str


class SessionSummaryResponse(BaseModel):
    """Structured, employee-friendly summary — replaces the original MVP's
    naive concatenation of assistant replies. See session_service.py."""

    session_id: str
    language: str = ""
    customer_issue: str = ""
    important_information: list[str] = []
    relevant_policy: str = ""
    recommended_next_action: str = ""
    unresolved: str = ""
    turns: list[TurnOut] = []
