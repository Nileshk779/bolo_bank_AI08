from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth.security import get_current_staff
from database.session import get_db
from schemas.chat import ChatRequest, ChatResponse
from services.ai_orchestrator import ai_orchestrator
from services.clarification_service import last_customer_question, plan
from services.session_service import log_turn

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, staff: str = Depends(get_current_staff), db: Session = Depends(get_db)):
    p = plan(req.text, req.complexity, last_customer_question(db, req.session_id))
    result = ai_orchestrator.handle_customer_query(text=p.query, language=req.language, complexity=p.complexity, followup=p.instruction)
    result.update(complexity_used=p.complexity, level_change=p.level_change, reexplained_question=p.reexplained_question)

    log_turn(db, req.session_id, "customer", req.language, req.text, "")
    log_turn(db, req.session_id, "assistant", req.language, result["reply_local"], result["reply_english"])

    return ChatResponse(**result)
