"""
BoloBank backend.

Endpoints:
  POST /api/transcribe   audio in  -> transcribed text (OpenAI Whisper)
  POST /api/chat         text in   -> AI reply text, using simple RAG over knowledge_base.json (Claude)
  POST /api/speak        text in   -> mp3 audio out (gTTS)
  POST /api/sessions/start   -> create a session
  POST /api/sessions/{id}/log -> log a turn to that session
  GET  /api/sessions/{id}/summary -> bilingual summary of the session
  POST /api/queue/token   -> generate a queue token
  GET  /api/queue         -> current queue status

Run locally:
  pip install -r requirements.txt
  cp .env.example .env   # then fill in your keys
  uvicorn main:app --reload --port 8000
"""

import json
import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import Column, DateTime, Integer, String, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

BASE_DIR = Path(__file__).parent
AUDIO_DIR = BASE_DIR / "audio_cache"
AUDIO_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Database (SQLite) — one row per conversation turn, for the audit trail
# ---------------------------------------------------------------------------
DB_PATH = BASE_DIR / "bolobank.db"
engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class Turn(Base):
    __tablename__ = "turns"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, index=True)
    role = Column(String)  # "customer" or "assistant"
    language = Column(String)
    text_local = Column(Text)
    text_english = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


Base.metadata.create_all(engine)

# ---------------------------------------------------------------------------
# Knowledge base (very small RAG — keyword overlap retrieval, no embeddings
# needed for the MVP; swap in a vector DB later if the doc set grows)
# ---------------------------------------------------------------------------
with open(BASE_DIR / "knowledge_base.json", encoding="utf-8") as f:
    KNOWLEDGE_BASE = json.load(f)


def retrieve_context(query: str, top_k: int = 2) -> str:
    query_words = set(query.lower().split())
    scored = []
    for doc in KNOWLEDGE_BASE:
        doc_words = set((doc["topic"] + " " + doc["content"]).lower().split())
        score = len(query_words & doc_words)
        scored.append((score, doc))
    scored.sort(key=lambda x: x[0], reverse=True)
    top_docs = [d for s, d in scored[:top_k] if s > 0] or [d for _, d in scored[:top_k]]
    return "\n\n".join(f"[{d['topic']}]\n{d['content']}" for d in top_docs)


LANGUAGE_NAMES = {
    "hi": "Hindi",
    "mr": "Marathi",
    "te": "Telugu",
    "kn": "Kannada",
    "en": "English",
}

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
app = FastAPI(title="BoloBank API")

origins = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# /api/transcribe — speech to text
# ---------------------------------------------------------------------------
@app.post("/api/transcribe")
async def transcribe(audio: UploadFile = File(...), language: str = Form("hi")):
    """Send recorded audio to Whisper and get back text in the customer's language."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(500, "OPENAI_API_KEY is not set on the server")

    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    tmp_path = AUDIO_DIR / f"{uuid.uuid4()}_{audio.filename}"
    with open(tmp_path, "wb") as f:
        f.write(await audio.read())

    try:
        with open(tmp_path, "rb") as f:
            result = client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                language=language if language != "auto" else None,
            )
        return {"text": result.text}
    finally:
        tmp_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# /api/chat — understand the question, answer using RAG + Claude
# ---------------------------------------------------------------------------
class ChatRequest(BaseModel):
    session_id: str
    text: str
    language: str = "hi"  # ISO code: hi, mr, te, kn, en


class ChatResponse(BaseModel):
    reply_local: str
    reply_english: str


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(500, "ANTHROPIC_API_KEY is not set on the server")

    from anthropic import Anthropic

    client = Anthropic(api_key=api_key)
    context = retrieve_context(req.text)
    lang_name = LANGUAGE_NAMES.get(req.language, "Hindi")

    system_prompt = (
        "You are BoloBank, a warm and patient banking assistant speaking with a customer "
        "at an Indian bank branch. Many customers are elderly or have low literacy, so keep "
        "sentences short, concrete, and free of jargon. Only use the bank policy context "
        "given below — never invent numbers, fees, or rules. If the context doesn't cover "
        "the question, say so plainly and suggest the customer speak with a staff member.\n\n"
        f"Bank policy context:\n{context}\n\n"
        f"Reply in {lang_name}. After your reply, on a new line starting with 'EN:', give a "
        "short English translation for the staff member to read."
    )

    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=400,
        system=system_prompt,
        messages=[{"role": "user", "content": req.text}],
    )

    raw = "".join(block.text for block in message.content if block.type == "text")
    if "EN:" in raw:
        local_part, english_part = raw.split("EN:", 1)
    else:
        local_part, english_part = raw, ""

    reply_local = local_part.strip()
    reply_english = english_part.strip()

    _log_turn(req.session_id, "customer", req.language, req.text, "")
    _log_turn(req.session_id, "assistant", req.language, reply_local, reply_english)

    return ChatResponse(reply_local=reply_local, reply_english=reply_english)


# ---------------------------------------------------------------------------
# /api/speak — text to speech
# ---------------------------------------------------------------------------
@app.post("/api/speak")
async def speak(text: str = Form(...), language: str = Form("hi")):
    from gtts import gTTS

    gtts_lang_map = {"hi": "hi", "mr": "mr", "te": "te", "kn": "kn", "en": "en"}
    lang = gtts_lang_map.get(language, "hi")

    filename = AUDIO_DIR / f"{uuid.uuid4()}.mp3"
    tts = gTTS(text=text, lang=lang)
    tts.save(str(filename))

    return FileResponse(filename, media_type="audio/mpeg", filename="reply.mp3")


# ---------------------------------------------------------------------------
# Sessions — audit log + bilingual summary
# ---------------------------------------------------------------------------
def _log_turn(session_id: str, role: str, language: str, text_local: str, text_english: str):
    db = SessionLocal()
    try:
        db.add(
            Turn(
                session_id=session_id,
                role=role,
                language=language,
                text_local=text_local,
                text_english=text_english,
            )
        )
        db.commit()
    finally:
        db.close()


@app.post("/api/sessions/start")
async def start_session(language: str = Form("hi")):
    session_id = str(uuid.uuid4())[:8]
    return {"session_id": session_id, "language": language}


@app.get("/api/sessions/{session_id}/summary")
async def session_summary(session_id: str):
    db = SessionLocal()
    try:
        turns = (
            db.query(Turn)
            .filter(Turn.session_id == session_id)
            .order_by(Turn.created_at)
            .all()
        )
    finally:
        db.close()

    if not turns:
        return {
            "session_id": session_id,
            "summary_english": "No interactions recorded in this session.",
            "summary_local": "",
            "turns": [],
        }

    turn_list = [
        {
            "role": t.role,
            "language": t.language,
            "text_local": t.text_local,
            "text_english": t.text_english,
            "created_at": t.created_at.isoformat(),
        }
        for t in turns
    ]

    english_lines = [t["text_english"] or t["text_local"] for t in turn_list if t["role"] == "assistant"]
    summary_english = " ".join(english_lines) or "Customer interaction recorded, see transcript."

    return {
        "session_id": session_id,
        "summary_english": summary_english,
        "turns": turn_list,
    }


# ---------------------------------------------------------------------------
# Simple in-memory queue management (swap for DB-backed queue in production)
# ---------------------------------------------------------------------------
QUEUE = []
TOKEN_COUNTER = 0


class TokenRequest(BaseModel):
    customer_name: str
    service_type: str
    customer_type: str = "general"  # general | elderly | rural


@app.post("/api/queue/token")
async def generate_token(req: TokenRequest):
    global TOKEN_COUNTER
    TOKEN_COUNTER += 1
    token = {
        "token": f"T{TOKEN_COUNTER:03d}",
        "customer_name": req.customer_name,
        "service_type": req.service_type,
        "customer_type": req.customer_type,
        "status": "waiting",
        "created_at": time.time(),
    }
    # Elderly customers are inserted ahead of general-queue waiters (priority lane)
    if req.customer_type == "elderly":
        insert_at = next((i for i, t in enumerate(QUEUE) if t["status"] == "waiting" and t["customer_type"] != "elderly"), len(QUEUE))
        QUEUE.insert(insert_at, token)
    else:
        QUEUE.append(token)
    return token


@app.get("/api/queue")
async def get_queue():
    return {
        "waiting": [t for t in QUEUE if t["status"] == "waiting"],
        "serving": [t for t in QUEUE if t["status"] == "serving"],
        "done": [t for t in QUEUE if t["status"] == "done"],
    }


@app.post("/api/queue/call-next")
async def call_next():
    for t in QUEUE:
        if t["status"] == "serving":
            t["status"] = "done"
    for t in QUEUE:
        if t["status"] == "waiting":
            t["status"] = "serving"
            return t
    return {"message": "Queue is empty"}


@app.get("/api/health")
async def health():
    return {"status": "ok"}
