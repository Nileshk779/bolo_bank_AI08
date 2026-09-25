import logging

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy.orm import Session

from auth.google_auth import GoogleAuthNotConfigured, verify_google_id_token
from auth.security import create_access_token, get_current_staff, verify_password
from core.config import settings
from database.models import Staff
from database.session import get_db
from schemas.auth import AuthConfigResponse, GoogleLoginRequest, LoginResponse
from services.rate_limit import limit_login

router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = logging.getLogger("bolobank.auth")


@router.post("/login", response_model=LoginResponse)
def login(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    limit_login(request, username)
    if not settings.ENABLE_PASSWORD_LOGIN:
        raise HTTPException(403, "Password login is disabled. Use Google Sign-In.")
    staff = db.query(Staff).filter(Staff.username == username).first()

    if not staff or not staff.password_hash or not verify_password(password, staff.password_salt, staff.password_hash):
        logger.warning("Failed login attempt for username=%s", username)
        raise HTTPException(401, "Incorrect username or password")

    token = create_access_token(staff.username)
    logger.info("Staff login: username=%s", username)
    return LoginResponse(access_token=token, display_name=staff.display_name)


@router.post("/google", response_model=LoginResponse)
def google_login(req: GoogleLoginRequest, request: Request, db: Session = Depends(get_db)):
    """Staff sign-in via Google. Flow:
      1. Verify the ID token server-side (signature, issuer, audience, expiry).
      2. Look up the verified email in the Staff table — this is the
         "authorized employee" check. Unknown emails are rejected; Google
         sign-in never auto-creates an account.
      3. Bind (or check) the Google account's stable subject id against the
         Staff row, so a later token for the same email but a different
         Google account is rejected.
      4. Issue our own JWT — identical in shape to the password-login token,
         so every other route in the app (get_current_staff, etc.) works
         the same regardless of which method was used to sign in.
    """
    limit_login(request)
    try:
        claims = verify_google_id_token(req.credential)
    except GoogleAuthNotConfigured:
        raise HTTPException(
            501, "Google sign-in is not configured on this server. Set GOOGLE_CLIENT_ID in the backend .env."
        )

    email = claims["email"]  # from the verified token only — never from request input
    staff = db.query(Staff).filter(Staff.email == email).first()

    if not staff:
        logger.warning("Google sign-in rejected — email not on the authorized employee list: %s", email)
        raise HTTPException(
            403,
            "This Google account is not authorized for BoloBank staff access. "
            "Ask your branch administrator to add your work email.",
        )

    if staff.google_sub and staff.google_sub != claims["sub"]:
        logger.warning("Google sign-in rejected — Google account mismatch for email=%s", email)
        raise HTTPException(403, "This Google account does not match our records for this employee.")

    if not staff.google_sub:
        staff.google_sub = claims["sub"]
        db.commit()

    token = create_access_token(staff.email)
    logger.info("Staff Google sign-in: email=%s", email)
    return LoginResponse(access_token=token, display_name=staff.display_name)


@router.get("/config", response_model=AuthConfigResponse)
async def auth_config():
    """Public (unauthenticated) — tells the frontend whether Google sign-in
    is available, without exposing anything secret. GOOGLE_CLIENT_ID itself
    isn't a secret (it's meant to be public), but this lets the frontend
    hide the button entirely if the server admin hasn't configured it."""
    return AuthConfigResponse(google_enabled=bool(settings.GOOGLE_CLIENT_ID), password_enabled=settings.ENABLE_PASSWORD_LOGIN)


@router.get("/me")
async def me(staff: str = Depends(get_current_staff)):
    return {"username": staff}
