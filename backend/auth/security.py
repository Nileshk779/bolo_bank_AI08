"""
Everything related to proving who the caller is — unchanged logic from the
original main.py, just relocated:
  - password hashing/verification (PBKDF2-HMAC-SHA256)
  - JWT session tokens
  - the get_current_staff dependency used to protect routes
"""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

import jwt
from fastapi import Header, HTTPException

from core.config import settings


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 100_000)
    return salt, digest.hex()


def verify_password(password: str, salt: str, expected_hash: str) -> bool:
    _, computed = hash_password(password, salt)
    return hmac.compare_digest(computed, expected_hash)


def create_access_token(username: str) -> str:
    payload = {"sub": username, "exp": datetime.utcnow() + timedelta(hours=settings.TOKEN_TTL_HOURS)}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def get_current_staff(authorization: str | None = Header(None)) -> str:
    """FastAPI dependency — every protected route requires a valid Bearer token."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing or invalid Authorization header")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Session expired, please log in again")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid session token")
    # Customer-portal tokens are signed with the same key; without this
    # check any customer (no login needed) could call staff-only routes.
    if payload.get("role") == "customer":
        raise HTTPException(403, "Staff session required")
    return payload["sub"]


def create_customer_token(session_id: str, language: str) -> str:
    """Short-lived token for the customer portal; separate from staff auth."""
    payload = {
        "sub": session_id,
        "role": "customer",
        "language": language,
        "exp": datetime.utcnow() + timedelta(hours=2),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def get_current_customer(authorization: str | None = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing or invalid customer session")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Customer session expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid customer session")
    if payload.get("role") != "customer":
        raise HTTPException(403, "Customer session required")
    return payload
