"""
Tests for Google Sign-In (staff auth).

Google's own token-signing/verification machinery is trusted, tested
upstream code (the `google-auth` library) and requires network access to
Google's cert endpoints that isn't available in CI/sandboxed environments,
so these tests mock BoloBank's thin `_verify_with_google` adapter at the external Google boundary and exercise
everything *our* code does with its result and its failures: the
authorized-employee check, account binding, and error mapping to HTTP
status codes. The audience/client-id argument passed to that call is
asserted directly, to confirm our code wires it correctly.
"""
from unittest.mock import patch

from tests.conftest import AUTHORIZED_EMAIL, SWAP_TEST_EMAIL, UNAUTHORIZED_EMAIL, google_claims

VERIFY_TARGET = "auth.google_auth._verify_with_google"


def test_valid_authorized_google_user_gets_a_session(client):
    with patch(VERIFY_TARGET, return_value=google_claims(AUTHORIZED_EMAIL)) as mock_verify:
        res = client.post("/api/auth/google", json={"credential": "fake-valid-token"})

    assert res.status_code == 200
    body = res.json()
    assert "access_token" in body and body["access_token"]
    assert body["token_type"] == "bearer"

    # Confirm our code passed the configured client ID as the audience to
    # verify against — this is what makes the "audience/client ID" check
    # actually happen.
    call_args = mock_verify.call_args.args
    assert call_args[1] == "test-client-id.apps.googleusercontent.com"

    # The issued JWT should actually work as a session token for a
    # protected route.
    token = body["access_token"]
    protected = client.get("/api/queue", headers={"Authorization": f"Bearer {token}"})
    assert protected.status_code == 200


def test_unauthorized_google_user_is_rejected(client):
    """A perfectly valid Google token for an email NOT on the employee
    allowlist must still be rejected — this is the core "unauthorized
    employee" requirement."""
    with patch(VERIFY_TARGET, return_value=google_claims(UNAUTHORIZED_EMAIL)):
        res = client.post("/api/auth/google", json={"credential": "fake-valid-token"})

    assert res.status_code == 403
    assert "not authorized" in res.json()["detail"].lower()


def test_google_account_swap_is_rejected(client):
    """Once an employee's email is bound to a Google account (sub), a
    different Google account claiming the same email must be rejected."""
    with patch(VERIFY_TARGET, return_value=google_claims(SWAP_TEST_EMAIL, sub="original-sub")):
        first = client.post("/api/auth/google", json={"credential": "token-1"})
    assert first.status_code == 200

    with patch(VERIFY_TARGET, return_value=google_claims(SWAP_TEST_EMAIL, sub="a-different-sub")):
        second = client.post("/api/auth/google", json={"credential": "token-2"})
    assert second.status_code == 403


def test_unverified_email_is_rejected(client):
    with patch(VERIFY_TARGET, return_value=google_claims(AUTHORIZED_EMAIL, email_verified=False)):
        res = client.post("/api/auth/google", json={"credential": "fake-token"})
    assert res.status_code == 401


def test_invalid_token_is_rejected(client):
    """google-auth raises ValueError for a malformed/tampered token."""
    with patch(VERIFY_TARGET, side_effect=ValueError("Wrong number of segments in token")):
        res = client.post("/api/auth/google", json={"credential": "not-a-real-token"})
    assert res.status_code == 401


def test_expired_token_is_rejected(client):
    """google-auth also raises ValueError (not a distinct exception type)
    for an expired token, so this is functionally the same code path as an
    invalid token — asserted separately since it's a distinct requirement."""
    with patch(VERIFY_TARGET, side_effect=ValueError("Token expired")):
        res = client.post("/api/auth/google", json={"credential": "expired-token"})
    assert res.status_code == 401


def test_missing_token_is_rejected(client):
    res = client.post("/api/auth/google", json={})
    assert res.status_code == 422  # Pydantic: `credential` is a required field


def test_protected_endpoint_without_authentication(client):
    res = client.get("/api/queue")
    assert res.status_code == 401


def test_protected_endpoint_with_garbage_token(client):
    res = client.get("/api/queue", headers={"Authorization": "Bearer not-a-real-jwt"})
    assert res.status_code == 401


# --- Regression checks: existing functionality must still work unchanged ---


def test_password_login_still_works(client):
    res = client.post("/api/auth/login", data={"username": "staff", "password": "bolobank123"})
    assert res.status_code == 200
    assert "access_token" in res.json()


def test_password_login_wrong_password_rejected(client):
    res = client.post("/api/auth/login", data={"username": "staff", "password": "wrong"})
    assert res.status_code == 401


def test_health_check(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_auth_config_reports_google_enabled(client):
    res = client.get("/api/auth/config")
    assert res.status_code == 200
    assert res.json() == {"google_enabled": True, "password_enabled": True}
