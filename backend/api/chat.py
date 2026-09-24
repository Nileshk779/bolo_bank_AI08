from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth.security import get_current_staff
from database.session import get_db
from schemas.chat import ChatRequest, ChatResponse
from services.ai_orchestrator import ai_orchestrator
from services.session_service import log_turn

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, staff: str = Depends(get_current_staff), db: Session = Depends(get_db)):
    result = ai_orchestrator.handle_customer_query(text=req.text, language=req.language, complexity=req.complexity)

    log_turn(db, req.session_id, "customer", req.language, req.text, "")
    log_turn(db, req.session_id, "assistant", req.language, result["reply_local"], result["reply_english"])

    return ChatResponse(**result)
