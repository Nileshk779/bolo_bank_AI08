"""
Test configuration.

Sets an isolated temp database and dummy secrets in the environment BEFORE
any application module is imported, so tests never touch the real
bolobank.db or require real GROQ/Google credentials to boot the app.
"""
import os
import sys
import tempfile
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["DATABASE_PATH"] = _tmp_db.name
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production-use-32ch")
os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-client-id.apps.googleusercontent.com")
os.environ.setdefault("ENABLE_PASSWORD_LOGIN", "true")
os.environ.setdefault("SCHEME_EXTRACTION_MODE", "preset")
os.environ.setdefault("SCHEME_AUTO_UPDATE", "false")
os.environ.setdefault("SEED_DEMO_STAFF", "true")
os.environ.setdefault("AUTHORIZED_EMPLOYEE_EMAILS", "authorized.teller@bolobank.co.in,swap.test@bolobank.co.in")

from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402

AUTHORIZED_EMAIL = "authorized.teller@bolobank.co.in"
SWAP_TEST_EMAIL = "swap.test@bolobank.co.in"  # dedicated email for the account-binding test, so it doesn't
# depend on execution order / state left behind by other tests sharing the session-scoped DB.
UNAUTHORIZED_EMAIL = "random.person@gmail.com"


@pytest.fixture(scope="session")
def client():
    return TestClient(app)


def google_claims(email: str, sub: str = "google-sub-12345", email_verified: bool = True, name: str = "Test User") -> dict:
    """Shape of what google.oauth2.id_token.verify_oauth2_token returns on success."""
    return {
        "iss": "https://accounts.google.com",
        "aud": os.environ["GOOGLE_CLIENT_ID"],
        "sub": sub,
        "email": email,
        "email_verified": email_verified,
        "name": name,
        "exp": 9999999999,
    }
