"""
Google ID token verification for staff sign-in.

The frontend never sends us an email address directly — it sends the signed
ID token that Google Identity Services issued after the user authenticated
with Google. This module verifies that token server-side and returns the
claims Google vouches for; every field the rest of the app trusts (email,
email_verified, sub) comes only from here, never from request JSON.
"""
import logging

from fastapi import HTTPException

from core.config import settings
from core.exceptions import UpstreamServiceError

logger = logging.getLogger("bolobank.google_auth")


class GoogleAuthNotConfigured(Exception):
    """Raised when GOOGLE_CLIENT_ID isn't set on the server."""


def _verify_with_google(credential: str, client_id: str) -> dict:
    """Thin adapter around google-auth, kept separate so unit tests can mock
    the network/crypto boundary without importing Google's package."""
    from google.auth import exceptions as google_exceptions
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token as google_id_token

    try:
        return google_id_token.verify_oauth2_token(
            credential, google_requests.Request(), client_id
        )
    except google_exceptions.TransportError as exc:
        raise UpstreamServiceError("Google Sign-In", str(exc)) from exc


def verify_google_id_token(credential: str) -> dict:
    """Verifies a Google ID token and returns {"sub", "email", "name"}.

    Verification (via google-auth's verify_oauth2_token) checks, using
    Google's published public keys:
      - signature validity
      - issuer is accounts.google.com / https://accounts.google.com
      - audience matches our GOOGLE_CLIENT_ID (rejects tokens issued for a
        different application)
      - the token has not expired

    Raises HTTPException(401) for any invalid/expired/malformed token,
    HTTPException(403) if the domain allowlist rejects it, or
    GoogleAuthNotConfigured if GOOGLE_CLIENT_ID isn't set.
    """
    if not settings.GOOGLE_CLIENT_ID:
        raise GoogleAuthNotConfigured()

    try:
        claims = _verify_with_google(credential, settings.GOOGLE_CLIENT_ID)
    except UpstreamServiceError:
        logger.error("Could not reach Google to verify sign-in token")
        raise
    except ValueError as exc:
        # verify_oauth2_token raises ValueError for every token-validity
        # failure mode: bad signature, wrong issuer, wrong audience,
        # expired, or malformed token.
        logger.warning("Google ID token verification failed: %s", exc)
        raise HTTPException(401, "Invalid or expired Google sign-in token")

    if not claims.get("email_verified"):
        raise HTTPException(401, "Google account email is not verified")

    email = (claims.get("email") or "").lower()
    if settings.GOOGLE_ALLOWED_DOMAIN and not email.endswith(f"@{settings.GOOGLE_ALLOWED_DOMAIN}"):
        logger.warning("Google sign-in rejected by domain allowlist: email=%s", email)
        raise HTTPException(403, "This Google account's domain is not authorized for BoloBank staff access")

    return {"sub": claims["sub"], "email": email, "name": claims.get("name") or email}
