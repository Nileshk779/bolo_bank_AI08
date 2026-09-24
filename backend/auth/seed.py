import logging

from auth.security import hash_password
from core.config import settings
from database.models import Staff
from database.session import SessionLocal

logger = logging.getLogger("bolobank.auth")


def seed_default_staff() -> None:
    if not settings.SEED_DEMO_STAFF:
        return
    db = SessionLocal()
    try:
        if db.query(Staff).count() == 0:
            salt, pw_hash = hash_password("bolobank123")
            db.add(Staff(username="staff", display_name="Branch Staff", password_salt=salt, password_hash=pw_hash))
            db.commit()
            logger.info("Seeded default staff account (username=staff)")
    finally:
        db.close()


def seed_authorized_employees() -> None:
    """Ensures every email in AUTHORIZED_EMPLOYEE_EMAILS has a Staff row it
    can bind to on first Google sign-in. This is the actual "authorized
    employee" mechanism: Google sign-in only ever succeeds for an email
    that's already present here — it never auto-creates a new staff
    account. Re-running this at every startup is safe (idempotent) and lets
    an admin authorize a new employee by adding their email to the env var
    and restarting."""
    if not settings.AUTHORIZED_EMPLOYEE_EMAILS:
        return

    db = SessionLocal()
    try:
        added = 0
        for email in settings.AUTHORIZED_EMPLOYEE_EMAILS:
            existing = db.query(Staff).filter(Staff.email == email).first()
            if existing:
                continue
            db.add(Staff(email=email, display_name=email.split("@")[0].replace(".", " ").title()))
            added += 1
        if added:
            db.commit()
            logger.info("Seeded %d authorized employee(s) for Google sign-in", added)
    finally:
        db.close()
