from fastapi import APIRouter, Depends

from auth.security import get_current_staff
from schemas.copilot import CopilotRequest, CopilotResponse
from services.ai_orchestrator import ai_orchestrator
from services.clarification_service import plan

router = APIRouter(prefix="/api", tags=["copilot"])


@router.post("/copilot", response_model=CopilotResponse)
async def copilot(req: CopilotRequest, staff: str = Depends(get_current_staff)):
    p = plan(req.query, req.complexity, req.previous_query)
    result = ai_orchestrator.handle_employee_query(query=p.query, language=req.language, complexity=p.complexity, followup=p.instruction)
    result.update(complexity_used=p.complexity, level_change=p.level_change, reexplained_question=p.reexplained_question)
    return CopilotResponse(**result)
