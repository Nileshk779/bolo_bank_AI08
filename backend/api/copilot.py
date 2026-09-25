import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth.security import get_current_staff
from schemas.copilot import CopilotRequest, CopilotResponse
from database.session import get_db
from services import analytics_service
from services.ai_orchestrator import ai_orchestrator
from services.llm_service import start_usage_tracking
from services.clarification_service import plan
from services.rate_limit import limit_staff_ai

router = APIRouter(prefix="/api", tags=["copilot"])


@router.post("/copilot", response_model=CopilotResponse, dependencies=[Depends(limit_staff_ai)])
def copilot(req: CopilotRequest, staff: str = Depends(get_current_staff), db: Session = Depends(get_db)):
    p = plan(req.query, req.complexity, req.previous_query)
    start_usage_tracking()
    result = ai_orchestrator.handle_employee_query(query=p.query, language=req.language, complexity=p.complexity, followup=p.instruction)
    # Copilot queries have no session; each counts as its own conversation.
    analytics_service.record_answer(db, channel="copilot", session_id=f"copilot-{uuid.uuid4().hex[:8]}", language=req.language,
                                    question=p.query, result=result, level_change=p.level_change)
    result.update(complexity_used=p.complexity, level_change=p.level_change, reexplained_question=p.reexplained_question)
    return CopilotResponse(**result)
