from pydantic import BaseModel


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    display_name: str


class GoogleLoginRequest(BaseModel):
    """The frontend sends only the raw ID token — never an email, name, or
    any other claim directly. Everything the backend trusts about who the
    user is comes from verifying this token server-side."""

    credential: str


class AuthConfigResponse(BaseModel):
    google_enabled: bool
    password_enabled: bool
