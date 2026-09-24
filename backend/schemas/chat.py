from typing import Any

from pydantic import BaseModel


class ChatRequest(BaseModel):
    session_id: str
    text: str
    language: str = "hi"  # ISO code: hi, mr, te, kn, en
    complexity: str = "simple"  # simple | normal | detailed
    elderly_mode: bool = False


class SourceRef(BaseModel):
    topic: str
    doc_id: str
    chunk_index: int
    score: float


class VisualData(BaseModel):
    """Screen-only structured data for a sensitive response — e.g. a
    balance, account number, or transaction. The customer's TTS never
    receives this; it exists only for on-screen display. See
    services/account_service.py and response_privacy_service.py."""

    type: str
    label: str
    value: Any
    currency: str | None = None


class ChatResponse(BaseModel):
    reply_local: str
    reply_english: str
    # Safe-for-TTS text. For a non-sensitive answer this equals reply_local;
    # for a sensitive one it's a generic "shown on screen" phrase and the
    # actual value lives only in visual_data, never in prose.
    spoken_response: str
    visual_data: VisualData | None = None
    sensitive: bool = False
    sources: list[SourceRef] = []
    confidence: float | None = None
    grounded: bool = True
    risk_level: str = "low"
    requires_human_review: bool = False
    # Optional UI hint, e.g. "open_eligibility" when the customer mentions
    # loans/schemes — the portal offers the eligibility checker.
    ui_action: str | None = None
    # Automatic explanation level (services/clarification_service.py):
    # the level actually used, and — when the customer said "I don't
    # understand" / "tell me more" — what changed and which earlier question
    # was answered again.
    complexity_used: str | None = None
    level_change: str | None = None  # "simpler" | "reexplain" | "more_detail"
    reexplained_question: str | None = None
