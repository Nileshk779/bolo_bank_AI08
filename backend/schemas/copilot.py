from pydantic import BaseModel

from schemas.chat import SourceRef, VisualData


class CopilotRequest(BaseModel):
    query: str
    language: str = "hi"
    complexity: str = "simple"


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
