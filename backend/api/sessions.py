from fastapi import APIRouter, Depends, Form
from sqlalchemy.orm import Session

from auth.security import get_current_staff
from database.session import get_db
from schemas.sessions import SessionSummaryResponse
from services.session_service import get_session_summary, new_session_id

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.post("/start")
async def start_session(language: str = Form("hi"), staff: str = Depends(get_current_staff)):
    return {"session_id": new_session_id(), "language": language}


@router.get("/{session_id}/summary", response_model=SessionSummaryResponse)
async def session_summary(session_id: str, staff: str = Depends(get_current_staff), db: Session = Depends(get_db)):
    return get_session_summary(db, session_id)
