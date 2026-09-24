from pydantic import BaseModel

from schemas.chat import SourceRef, VisualData


class CopilotRequest(BaseModel):
    query: str
    language: str = "hi"
    complexity: str = "simple"
    # The previous Copilot query, so "customer didn't understand" can redo it.
    previous_query: str | None = None


class CopilotResponse(BaseModel):
    understood_summary: str
    relevant_info: str
    suggested_action: str
    suggested_reply_local: str
    suggested_reply_english: str
    # Safe-for-TTS text for the "speak to customer" button — see ChatResponse.
    spoken_response: str
    visual_data: VisualData | None = None
    sensitive: bool = False
    sources: list[SourceRef] = []
    confidence: float | None = None
    grounded: bool = True
    risk_level: str = "low"
    requires_human_review: bool = False
    # Automatic explanation level (services/clarification_service.py):
    # the level actually used, and — when the customer said "I don't
    # understand" / "tell me more" — what changed and which earlier question
    # was answered again.
    complexity_used: str | None = None
    level_change: str | None = None  # "simpler" | "reexplain" | "more_detail"
    reexplained_question: str | None = None
