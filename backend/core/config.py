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
    # --- Core secret ---
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-only-secret-change-me")

    # --- LLM / STT provider ---
    GROQ_API_KEY: str | None = os.getenv("GROQ_API_KEY")

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
    SCHEME_EXTRACTION_MODE: str = os.getenv("SCHEME_EXTRACTION_MODE", "llm").lower()

    # --- CORS ---
    CORS_ORIGINS: list[str] = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")

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
