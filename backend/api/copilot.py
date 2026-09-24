from fastapi import APIRouter, Depends

from auth.security import get_current_staff
from schemas.copilot import CopilotRequest, CopilotResponse
from services.ai_orchestrator import ai_orchestrator

router = APIRouter(prefix="/api", tags=["copilot"])


@router.post("/copilot", response_model=CopilotResponse)
async def copilot(req: CopilotRequest, staff: str = Depends(get_current_staff)):
    result = ai_orchestrator.handle_employee_query(query=req.query, language=req.language, complexity=req.complexity)
    return CopilotResponse(**result)
