from pydantic import BaseModel
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from auth.security import create_customer_token, get_current_customer
from database.session import get_db
from schemas.chat import ChatRequest, ChatResponse
from schemas.eligibility import EligibilityRequest, EligibilityResponse
from services.ai_orchestrator import ai_orchestrator
from services.eligibility_service import check_eligibility, describe_profile_english, detect_loan_interest
from services.response_privacy_service import protect_for_speech
from services.scheme_update_service import get_approved_schemes
from services.session_service import log_turn, new_session_id
from services.speech_service import transcribe_upload
from services.tts_service import synthesize_speech

router = APIRouter(prefix="/api/customer", tags=["customer-portal"])

class CustomerSessionRequest(BaseModel):
    language: str = "mr"

@router.post("/session/start")
async def start_customer_session(req: CustomerSessionRequest):
    if req.language not in {"en", "hi", "mr", "kn", "te"}:
        raise HTTPException(400, "Unsupported language")
    session_id = new_session_id()
    return {"session_id": session_id, "language": req.language, "customer_token": create_customer_token(session_id, req.language)}

@router.post("/chat", response_model=ChatResponse)
async def customer_chat(req: ChatRequest, customer: dict = Depends(get_current_customer), db: Session = Depends(get_db)):
    if req.session_id != customer.get("sub"):
        raise HTTPException(403, "Session mismatch")
    language = customer.get("language", req.language)
    result = ai_orchestrator.handle_customer_query(text=req.text, language=language, complexity=req.complexity)
    log_turn(db, req.session_id, "customer", language, req.text, "")
    log_turn(db, req.session_id, "assistant", language, result["reply_local"], result["reply_english"])
    if detect_loan_interest(req.text):
        result["ui_action"] = "open_eligibility"
    return ChatResponse(**result)

@router.post("/eligibility", response_model=EligibilityResponse)
async def customer_eligibility(req: EligibilityRequest, customer: dict = Depends(get_current_customer), db: Session = Depends(get_db)):
    if req.session_id != customer.get("sub"):
        raise HTTPException(403, "Session mismatch")
    language = customer.get("language", "en")
    assets = req.assets.model_dump()
    result = check_eligibility(assets, req.occupation, req.purpose, req.age, language, extra_schemes=get_approved_schemes(db))
    # Logged in English so the staff Copilot/summary can see what the
    # customer asked for and which schemes were suggested for review.
    profile = describe_profile_english(assets, req.occupation, req.purpose, req.age)
    names = ", ".join(m["name_english"] for m in result["matches"]) or "none — refer to staff"
    log_turn(db, req.session_id, "customer", language, profile, profile)
    log_turn(db, req.session_id, "assistant", language, f"Possible schemes: {names}", f"Possible schemes (pre-check, staff to confirm): {names}")
    return EligibilityResponse(**result)

@router.post("/transcribe")
async def customer_transcribe(audio: UploadFile = File(...), language: str = Form("mr"), customer: dict = Depends(get_current_customer)):
    language = customer.get("language", language)
    return {"text": await transcribe_upload(audio, language)}

@router.post("/speak")
async def customer_speak(background_tasks: BackgroundTasks, text: str = Form(...), language: str = Form("mr"), elderly_mode: bool = Form(False), customer: dict = Depends(get_current_customer)):
    language = customer.get("language", language)
    safe_text = protect_for_speech(text, language=language).safe_text
    filename = synthesize_speech(safe_text, language=language, slow=elderly_mode)
    background_tasks.add_task(lambda: filename.unlink(missing_ok=True))
    return FileResponse(filename, media_type="audio/mpeg", filename="reply.mp3", background=background_tasks)
