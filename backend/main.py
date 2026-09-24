"""
BoloBank backend — modular monolith.

Same endpoints and behavior as the original single-file MVP, reorganized
into: api/ (routes) -> services/ (business logic) -> database/ (data
access), with auth/, schemas/, and core/ (config, logging, exceptions) as
supporting layers. See README.md for the full architecture note.

Endpoints (unchanged from the original MVP, plus Google Sign-In additions):
  POST /api/auth/login       staff username+password -> JWT access token
  POST /api/auth/google      staff Google ID token -> JWT access token (see auth/google_auth.py)
  GET  /api/auth/config      public — tells the frontend whether Google sign-in is configured
  POST /api/transcribe       audio in  -> transcribed text (Groq Whisper)          [auth required]
  POST /api/chat             text in   -> AI reply, complexity-adjustable          [auth required]
  POST /api/copilot          employee query -> understanding + suggested action    [auth required]
  POST /api/speak            text in   -> mp3 audio out (gTTS)                     [auth required]
  POST /api/sessions/start   -> create a session                                   [auth required]
  GET  /api/sessions/{id}/summary -> bilingual summary of the session              [auth required]
  POST /api/queue/token      -> generate a queue token                             [auth required]
  GET  /api/queue            -> current queue status                               [auth required]
  POST /api/queue/call-next  -> advance the queue                                  [auth required]
  GET  /api/health           -> liveness check
  /api/customer/eligibility  -> loan/scheme eligibility pre-check           [customer session]
  /api/schemes/updates/...   -> daily scheme updates + staff approval       [auth required]

Optional local demo password login is disabled by default. Enable it only for local/demo use via .env.

Run locally:
  pip install -r requirements.txt
  cp .env.example .env   # then fill in your keys
  uvicorn main:app --reload --port 8000
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import auth, chat, copilot, customer, demo_data, health, queue, schemes, sessions, voice
from auth.seed import seed_authorized_employees, seed_default_staff
from core.config import settings
from core.exceptions import register_exception_handlers
from core.logging import setup_logging
from database.models import Base
from database.session import SessionLocal, engine
from services.rag_service import retriever
from services.scheme_update_service import run_update

setup_logging()
logger = logging.getLogger("bolobank.main")
settings.validate_runtime_security()

Base.metadata.create_all(engine)
seed_default_staff()
seed_authorized_employees()



def _scheduled_scheme_update() -> None:
    db = SessionLocal()
    try:
        run = run_update(db, trigger="scheduled")
        logger.info("Scheme update: %s items seen, %s new drafts for staff review", run.items_seen, run.new_drafts)
    finally:
        db.close()


async def _scheme_update_loop() -> None:
    """Checks for new schemes at startup and then every
    SCHEME_UPDATE_INTERVAL_HOURS. New schemes only become drafts — staff
    approve them in the Staff Portal before customers see them."""
    while True:
        try:
            await asyncio.to_thread(_scheduled_scheme_update)
        except Exception:
            logger.exception("Scheduled scheme update failed")
        await asyncio.sleep(settings.SCHEME_UPDATE_INTERVAL_HOURS * 3600)


async def _warm_up_retrieval() -> None:
    """Loads the embedding model and builds the knowledge-base index in the
    background at startup (~8 s), so the first customer question isn't slow."""
    try:
        await asyncio.to_thread(retriever.retrieve, "warm up")
        logger.info("Knowledge-base search index ready")
    except Exception:
        logger.exception("Knowledge-base warm-up failed; the index will be built on the first question instead")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    task = asyncio.create_task(_scheme_update_loop()) if settings.SCHEME_AUTO_UPDATE else None
    warm_up = asyncio.create_task(_warm_up_retrieval())
    yield
    warm_up.cancel()
    if task:
        task.cancel()


app = FastAPI(title="BoloBank API", lifespan=lifespan)
register_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(customer.router)
app.include_router(voice.router)
app.include_router(chat.router)
app.include_router(copilot.router)
app.include_router(sessions.router)
app.include_router(queue.router)
app.include_router(health.router)
app.include_router(demo_data.router)
app.include_router(schemes.router)

logger.info("BoloBank API started")
