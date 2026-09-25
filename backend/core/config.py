"""
Centralized configuration. Every environment variable used by the app is
read here, once, instead of scattered os.getenv() calls throughout the
codebase (which is how the original single-file main.py did it).
"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
AUDIO_DIR = BASE_DIR / "audio_cache"
AUDIO_DIR.mkdir(exist_ok=True)
# `or` (not a getenv default) so an empty DATABASE_PATH= line in .env also
# falls back to the default file instead of an unopenable empty path.
DB_PATH = Path(os.getenv("DATABASE_PATH") or str(BASE_DIR / "bolobank.db"))
KNOWLEDGE_BASE_PATH = BASE_DIR / "data" / "bank_knowledge.json"


class Settings:
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development").lower()

    # --- Database (database/session.py) ---
    # Empty = SQLite file at DATABASE_PATH. Production: PostgreSQL, e.g.
    #   postgresql+psycopg://bolobank:password@db-host:5432/bolobank
    DATABASE_URL: str = os.getenv("DATABASE_URL") or f"sqlite:///{DB_PATH}"
    DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE") or "20")
    DB_MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW") or "50")
    # Apply database migrations when the app starts. Keep on for local use;
    # in production run "alembic upgrade head" once per deploy instead and
    # set this to false, so several server processes don't race.
    AUTO_MIGRATE: bool = os.getenv("AUTO_MIGRATE", "true").lower() in {"1", "true", "yes", "on"}
    # --- Core secret ---
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-only-secret-change-me")

    # --- LLM / STT provider ---
    GROQ_API_KEY: str | None = os.getenv("GROQ_API_KEY")
    # Chat model. Groq retires models over time (llama-3.3-70b-versatile is no
    # longer offered), so this is configurable. List what your key can use:
    #   python -c "from groq import Groq; print([m.id for m in Groq().models.list().data])"
    GROQ_CHAT_MODEL: str = os.getenv("GROQ_CHAT_MODEL") or "openai/gpt-oss-120b"
    # Used when the main model fails (rate limit, outage, retired model).
    # Set to the same value as GROQ_CHAT_MODEL, or empty, to disable.
    GROQ_FALLBACK_MODEL: str = os.getenv("GROQ_FALLBACK_MODEL", "openai/gpt-oss-20b")
    # Give up on a slow AI call instead of tying up a worker thread; the SDK
    # retries rate-limit (429), server and connection errors with backoff.
    LLM_TIMEOUT_SECONDS: float = float(os.getenv("LLM_TIMEOUT_SECONDS") or "30")
    LLM_MAX_RETRIES: int = int(os.getenv("LLM_MAX_RETRIES") or "2")
    # Prices for the dashboard's AI-cost estimate (USD per 1M tokens) and the
    # exchange rate. Defaults are assumptions — check groq.com/pricing and
    # set the current values in .env.
    LLM_PRICE_INPUT_PER_M_USD: float = float(os.getenv("LLM_PRICE_INPUT_PER_M_USD") or "0.15")
    LLM_PRICE_OUTPUT_PER_M_USD: float = float(os.getenv("LLM_PRICE_OUTPUT_PER_M_USD") or "0.75")
    # Branch time zone for the dashboard's days (minutes east of UTC; India = 330).
    BRANCH_UTC_OFFSET_MINUTES: int = int(os.getenv("BRANCH_UTC_OFFSET_MINUTES") or "330")
    USD_TO_INR: float = float(os.getenv("USD_TO_INR") or "88")

    # --- Auth / sessions ---
    TOKEN_TTL_HOURS: int = int(os.getenv("TOKEN_TTL_HOURS", "12"))
    ENABLE_PASSWORD_LOGIN: bool = os.getenv("ENABLE_PASSWORD_LOGIN", "false").lower() in {"1", "true", "yes", "on"}
    SEED_DEMO_STAFF: bool = os.getenv("SEED_DEMO_STAFF", "false").lower() in {"1", "true", "yes", "on"}

    # --- Google Sign-In for staff ---
    # Create an OAuth 2.0 Client ID (type: Web application) in Google Cloud
    # Console -> APIs & Services -> Credentials. Add your frontend origin
    # (e.g. http://localhost:5173) to "Authorized JavaScript origins".
    # The SAME client id must also be set on the frontend as
    # VITE_GOOGLE_CLIENT_ID. There is no client *secret* to configure here —
    # Google Identity Services' ID-token flow never generates one, so
    # nothing secret is ever sent to or stored in the frontend.
    GOOGLE_CLIENT_ID: str | None = os.getenv("GOOGLE_CLIENT_ID")

    # Optional defense-in-depth: only allow sign-in from Google accounts on
    # this email domain (e.g. bolobank.co.in). Leave unset to skip this
    # check — the per-employee allowlist below is the primary control.
    GOOGLE_ALLOWED_DOMAIN: str | None = os.getenv("GOOGLE_ALLOWED_DOMAIN")

    # Comma-separated allowlist of employee email addresses authorized to
    # sign in with Google. Seeded into the Staff table at startup (see
    # auth/seed.py) — an email must already be provisioned here (i.e.
    # already exist as a Staff row) before its Google account is trusted.
    # This is the actual "authorized employee" mechanism: signing in with
    # Google never auto-creates a new staff account.
    AUTHORIZED_EMPLOYEE_EMAILS: list[str] = [
        e.strip().lower() for e in os.getenv("AUTHORIZED_EMPLOYEE_EMAILS", "").split(",") if e.strip()
    ]

    # --- Daily scheme updates (services/scheme_update_service.py) ---
    # The job runs once at startup and then every SCHEME_UPDATE_INTERVAL_HOURS.
    SCHEME_AUTO_UPDATE: bool = os.getenv("SCHEME_AUTO_UPDATE", "true").lower() in {"1", "true", "yes", "on"}
    SCHEME_UPDATE_INTERVAL_HOURS: float = float(os.getenv("SCHEME_UPDATE_INTERVAL_HOURS", "24"))
    # "llm" = extract each announcement with the Groq LLM (falls back to the
    # feed's demo preset on error); "preset" = never call the LLM.
    # How long an approved scheme is announced as "new" to customers.
    NEW_SCHEME_DAYS: int = int(os.getenv("NEW_SCHEME_DAYS") or "30")
    SCHEME_EXTRACTION_MODE: str = os.getenv("SCHEME_EXTRACTION_MODE", "llm").lower()

    # --- Capacity (Phase 1 scaling) ---
    # Threads per server process for blocking work (AI, speech, database).
    # AI calls mostly wait on the network, so this can exceed the CPU count.
    WORKER_THREADS: int = int(os.getenv("WORKER_THREADS") or "64")

    # Largest accepted voice recording. A spoken question is well under 1 MB.
    MAX_AUDIO_UPLOAD_MB: float = float(os.getenv("MAX_AUDIO_UPLOAD_MB") or "5")

    # --- Redis (optional; services/redis_client.py) ---
    # Shares rate limits and caches across server processes, e.g.
    # redis://localhost:6379/0 . Empty = each process keeps its own in memory.
    REDIS_URL: str = os.getenv("REDIS_URL", "")
    REDIS_PREFIX: str = os.getenv("REDIS_PREFIX", "bolobank:")

    # --- Caches (services/answer_cache.py, services/tts_service.py) ---
    ANSWER_CACHE_ENABLED: bool = os.getenv("ANSWER_CACHE_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
    ANSWER_CACHE_SIMILARITY: float = float(os.getenv("ANSWER_CACHE_SIMILARITY") or "0.97")
    ANSWER_CACHE_TTL_SECONDS: int = int(os.getenv("ANSWER_CACHE_TTL_SECONDS") or str(24 * 3600))
    ANSWER_CACHE_MAX_ENTRIES: int = int(os.getenv("ANSWER_CACHE_MAX_ENTRIES") or "5000")
    TTS_CACHE_ENABLED: bool = os.getenv("TTS_CACHE_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
    TTS_CACHE_MAX_ENTRIES: int = int(os.getenv("TTS_CACHE_MAX_ENTRIES") or "500")
    TTS_CACHE_TTL_SECONDS: int = int(os.getenv("TTS_CACHE_TTL_SECONDS") or str(7 * 24 * 3600))  # Redis only
    ANSWER_CACHE_PER_BUCKET: int = int(os.getenv("ANSWER_CACHE_PER_BUCKET") or "200")  # Redis only

    # --- Rate limits (per minute; services/rate_limit.py) ---
    RATE_LIMIT_ENABLED: bool = os.getenv("RATE_LIMIT_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
    RATE_LIMIT_CUSTOMER_AI_PER_MIN: int = int(os.getenv("RATE_LIMIT_CUSTOMER_AI_PER_MIN") or "20")
    RATE_LIMIT_CUSTOMER_SPEECH_PER_MIN: int = int(os.getenv("RATE_LIMIT_CUSTOMER_SPEECH_PER_MIN") or "40")
    RATE_LIMIT_STAFF_AI_PER_MIN: int = int(os.getenv("RATE_LIMIT_STAFF_AI_PER_MIN") or "60")
    # Ceiling per IP address — generous, because a branch kiosk puts many
    # customers behind one address.
    RATE_LIMIT_IP_AI_PER_MIN: int = int(os.getenv("RATE_LIMIT_IP_AI_PER_MIN") or "300")
    RATE_LIMIT_SESSION_START_PER_MIN: int = int(os.getenv("RATE_LIMIT_SESSION_START_PER_MIN") or "30")
    RATE_LIMIT_PUBLIC_PER_MIN: int = int(os.getenv("RATE_LIMIT_PUBLIC_PER_MIN") or "60")
    RATE_LIMIT_LOGIN_PER_MIN: int = int(os.getenv("RATE_LIMIT_LOGIN_PER_MIN") or "10")
    RATE_LIMIT_LOGIN_PER_USER_PER_MIN: int = int(os.getenv("RATE_LIMIT_LOGIN_PER_USER_PER_MIN") or "5")
    # Only when running behind your own reverse proxy / load balancer:
    # use the X-Forwarded-For header as the client address.
    TRUST_PROXY_HEADERS: bool = os.getenv("TRUST_PROXY_HEADERS", "false").lower() in {"1", "true", "yes", "on"}

    # --- CORS ---
    CORS_ORIGINS: list[str] = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")

    # --- Monitoring (services/metrics.py) ---
    # If set, GET /metrics requires "Authorization: Bearer <token>".
    METRICS_TOKEN: str = os.getenv("METRICS_TOKEN", "")
    # "text" (readable) or "json" (one JSON object per line, for log collectors).
    LOG_FORMAT: str = os.getenv("LOG_FORMAT", "text").lower()

    # --- Logging ---
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    @property
    def using_default_secret(self) -> bool:
        return self.SECRET_KEY == "dev-only-secret-change-me"

    def validate_runtime_security(self) -> None:
        if self.ENVIRONMENT == "production":
            if self.using_default_secret:
                raise RuntimeError("SECRET_KEY must be explicitly configured in production")
            if self.SEED_DEMO_STAFF:
                raise RuntimeError("SEED_DEMO_STAFF must be disabled in production")


settings = Settings()
