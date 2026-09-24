"""
BoloBank backend.

Uses Groq's free API for both the LLM (Llama 3.3 70B) and speech-to-text
(Whisper large-v3-turbo) — one free key, no credit card required.
Get a key at https://console.groq.com/keys

Endpoints:
  POST /api/auth/login       staff username+password -> JWT access token
  POST /api/transcribe       audio in  -> transcribed text (Groq Whisper)          [auth required]
  POST /api/chat             text in   -> AI reply, complexity-adjustable          [auth required]
  POST /api/copilot          employee query -> understanding + suggested action    [auth required]
                              + drafted customer-facing reply (employee stays in control)
  POST /api/speak            text in   -> mp3 audio out (gTTS)                     [auth required]
  POST /api/sessions/start   -> create a session                                   [auth required]
  GET  /api/sessions/{id}/summary -> bilingual summary of the session              [auth required]
  POST /api/queue/token      -> generate a queue token                             [auth required]
  GET  /api/queue            -> current queue status                               [auth required]

Default login (change this before any real deployment):
  username: staff
  password: bolobank123

Run locally:
  pip install -r requirements.txt
  cp .env.example .env   # then fill in your keys
  uvicorn main:app --reload --port 8000
"""

import hashlib
import hmac
import json
import os
import secrets
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import jwt
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import Column, DateTime, Integer, String, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

BASE_DIR = Path(__file__).parent
AUDIO_DIR = BASE_DIR / "audio_cache"
AUDIO_DIR.mkdir(exist_ok=True)

SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-secret-change-me")
TOKEN_TTL_HOURS = 12

# ---------------------------------------------------------------------------
# Database (SQLite) — conversation turns (audit trail) + staff accounts
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


class Staff(Base):
    __tablename__ = "staff"
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, unique=True, index=True)
    display_name = Column(String)
    password_salt = Column(String)
    password_hash = Column(String)


Base.metadata.create_all(engine)


# ---------------------------------------------------------------------------
# Auth — password hashing (stdlib only, no native deps) + JWT session tokens
# ---------------------------------------------------------------------------
def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 100_000)
    return salt, digest.hex()


def verify_password(password: str, salt: str, expected_hash: str) -> bool:
    _, computed = hash_password(password, salt)
    return hmac.compare_digest(computed, expected_hash)


def _seed_default_staff():
    db = SessionLocal()
    try:
        if db.query(Staff).count() == 0:
            salt, pw_hash = hash_password("bolobank123")
            db.add(Staff(username="staff", display_name="Branch Staff", password_salt=salt, password_hash=pw_hash))
            db.commit()
    finally:
        db.close()


_seed_default_staff()


def create_access_token(username: str) -> str:
    payload = {"sub": username, "exp": datetime.utcnow() + timedelta(hours=TOKEN_TTL_HOURS)}
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def get_current_staff(authorization: str | None = Header(None)) -> str:
    """FastAPI dependency — every protected route requires a valid Bearer token."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing or invalid Authorization header")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Session expired, please log in again")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid session token")
    return payload["sub"]


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

# "Explain Like I'm 60" — complexity presets that reshape how the AI explains
# banking concepts, aimed at elderly / low-literacy customers.
COMPLEXITY_INSTRUCTIONS = {
    "simple": (
        "Explain like you're talking to a 60-year-old customer with no banking or "
        "financial background. Use very short sentences (under 12 words each). Avoid "
        "all jargon — no words like 'interest rate', 'reducing balance', 'KYC', etc. "
        "without immediately explaining them in plain everyday language with a small "
        "example. Use warm, respectful, patient tone, like a helpful grandchild "
        "explaining something to a grandparent."
    ),
    "normal": (
        "Explain clearly and politely, as you would to an adult customer with some "
        "everyday familiarity with banking. You can use standard banking terms, but "
        "briefly clarify any term a first-time customer might not know."
    ),
    "detailed": (
        "Give a precise, complete explanation suitable for a customer who wants full "
        "detail — include exact terms, relevant numbers from the policy context, and "
        "any conditions or exceptions that apply."
    ),
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


def _get_groq_client():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(500, "GROQ_API_KEY is not set on the server")
    from groq import Groq

    return Groq(api_key=api_key)


# ---------------------------------------------------------------------------
# /api/auth/login — staff sign-in
# ---------------------------------------------------------------------------
class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    display_name: str


@app.post("/api/auth/login", response_model=LoginResponse)
async def login(username: str = Form(...), password: str = Form(...)):
    db = SessionLocal()
    try:
        staff = db.query(Staff).filter(Staff.username == username).first()
    finally:
        db.close()

    if not staff or not verify_password(password, staff.password_salt, staff.password_hash):
        raise HTTPException(401, "Incorrect username or password")

    token = create_access_token(staff.username)
    return LoginResponse(access_token=token, display_name=staff.display_name)


@app.get("/api/auth/me")
async def me(staff: str = Depends(get_current_staff)):
    return {"username": staff}


# ---------------------------------------------------------------------------
# /api/transcribe — speech to text
# ---------------------------------------------------------------------------
@app.post("/api/transcribe")
async def transcribe(
    audio: UploadFile = File(...),
    language: str = Form("hi"),
    staff: str = Depends(get_current_staff),
):
    """Send recorded audio to Groq's free Whisper endpoint and get back text."""
    client = _get_groq_client()
    tmp_path = AUDIO_DIR / f"{uuid.uuid4()}_{audio.filename}"
    with open(tmp_path, "wb") as f:
        f.write(await audio.read())

    try:
        with open(tmp_path, "rb") as f:
            result = client.audio.transcriptions.create(
                model="whisper-large-v3-turbo",
                file=f,
                language=language if language != "auto" else None,
            )
        return {"text": result.text}
    finally:
        tmp_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# /api/chat — understand the question, answer using RAG + Groq
# ---------------------------------------------------------------------------
class ChatRequest(BaseModel):
    session_id: str
    text: str
    language: str = "hi"  # ISO code: hi, mr, te, kn, en
    complexity: str = "simple"  # simple | normal | detailed


class ChatResponse(BaseModel):
    reply_local: str
    reply_english: str


def _build_chat_system_prompt(context: str, lang_name: str, complexity: str) -> str:
    complexity_instruction = COMPLEXITY_INSTRUCTIONS.get(complexity, COMPLEXITY_INSTRUCTIONS["simple"])
    return (
        "You are BoloBank, a warm and patient banking assistant speaking with a customer "
        "at an Indian bank branch. Only use the bank policy context given below — never "
        "invent numbers, fees, or rules. If the context doesn't cover the question, say so "
        "plainly and suggest the customer speak with a staff member.\n\n"
        f"Explanation style: {complexity_instruction}\n\n"
        f"Bank policy context:\n{context}\n\n"
        f"Reply in {lang_name}. After your reply, on a new line starting with 'EN:', give a "
        "short English translation for the staff member to read."
    )


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, staff: str = Depends(get_current_staff)):
    client = _get_groq_client()
    context = retrieve_context(req.text)
    lang_name = LANGUAGE_NAMES.get(req.language, "Hindi")
    system_prompt = _build_chat_system_prompt(context, lang_name, req.complexity)

    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=400,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": req.text},
        ],
    )

    raw = completion.choices[0].message.content or ""
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
# /api/copilot — AI Employee Copilot
#
# Unlike /api/chat (which talks directly to the customer), this endpoint is
# for the STAFF MEMBER: it takes a customer's question (typed by staff, or
# pulled from a transcript), and returns a structured briefing — what the
# customer wants, the relevant policy, a suggested next action, and a DRAFT
# reply in the customer's language that staff can edit before it's spoken.
# The employee stays in control: nothing is sent to the customer automatically.
# ---------------------------------------------------------------------------
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


@app.post("/api/copilot", response_model=CopilotResponse)
async def copilot(req: CopilotRequest, staff: str = Depends(get_current_staff)):
    client = _get_groq_client()
    context = retrieve_context(req.query)
    lang_name = LANGUAGE_NAMES.get(req.language, "Hindi")
    complexity_instruction = COMPLEXITY_INSTRUCTIONS.get(req.complexity, COMPLEXITY_INSTRUCTIONS["simple"])

    system_prompt = (
        "You are an AI copilot for a bank branch employee (not the customer). The "
        "employee has a customer in front of them asking a question, possibly in a "
        "regional Indian language. Your job is to brief the employee quickly and "
        "accurately, and to draft (never send) a customer-facing reply they can review, "
        "edit, and approve.\n\n"
        "Only use the bank policy context given below — never invent numbers, fees, or "
        "rules. If the context doesn't cover the question, say so plainly.\n\n"
        f"Bank policy context:\n{context}\n\n"
        f"Draft reply style: {complexity_instruction}\n\n"
        "Respond with ONLY a JSON object (no markdown fences, no extra text) with "
        "exactly these keys:\n"
        '  "understood_summary": one short sentence in English restating what the '
        "customer wants.\n"
        '  "relevant_info": 2-4 short bullet points (as a single string, '
        "newline-separated) of the relevant policy facts the employee needs.\n"
        '  "suggested_action": one concrete next step the employee should take '
        "(e.g. which form to pull up, what document to ask for, whether to escalate).\n"
        f'  "reply_local": a customer-facing reply written in {lang_name}, following '
        "the draft reply style above.\n"
        '  "reply_english": the English translation of reply_local, for the employee '
        "to double-check before it's spoken aloud."
    )

    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=500,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": req.query},
        ],
        response_format={"type": "json_object"},
    )

    raw = completion.choices[0].message.content or "{}"
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = {}

    return CopilotResponse(
        understood_summary=parsed.get("understood_summary", "").strip(),
        relevant_info=parsed.get("relevant_info", "").strip(),
        suggested_action=parsed.get("suggested_action", "").strip(),
        suggested_reply_local=parsed.get("reply_local", "").strip(),
        suggested_reply_english=parsed.get("reply_english", "").strip(),
    )


# ---------------------------------------------------------------------------
# /api/speak — text to speech
# ---------------------------------------------------------------------------
@app.post("/api/speak")
async def speak(text: str = Form(...), language: str = Form("hi"), staff: str = Depends(get_current_staff)):
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
async def start_session(language: str = Form("hi"), staff: str = Depends(get_current_staff)):
    session_id = str(uuid.uuid4())[:8]
    return {"session_id": session_id, "language": language}


@app.get("/api/sessions/{session_id}/summary")
async def session_summary(session_id: str, staff: str = Depends(get_current_staff)):
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
async def generate_token(req: TokenRequest, staff: str = Depends(get_current_staff)):
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
async def get_queue(staff: str = Depends(get_current_staff)):
    return {
        "waiting": [t for t in QUEUE if t["status"] == "waiting"],
        "serving": [t for t in QUEUE if t["status"] == "serving"],
        "done": [t for t in QUEUE if t["status"] == "done"],
    }


@app.post("/api/queue/call-next")
async def call_next(staff: str = Depends(get_current_staff)):
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
