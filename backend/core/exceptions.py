"""
Application-level exceptions + a global handler for anything unhandled.

The original main.py relied entirely on ad-hoc HTTPException(...) calls
inside route handlers and let anything else (e.g. an unexpected Groq/gTTS
error) surface as FastAPI's default 500 with a raw traceback-shaped
response. Route handlers still raise HTTPException for expected, specific
error cases (unchanged) — this module adds a safety net so any *unexpected*
exception is logged with context and returned as a clean, consistent JSON
error instead of leaking internals to the client.
"""
import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("bolobank.exceptions")


class UpstreamServiceError(Exception):
    """Raised when a downstream dependency (Groq LLM/STT, gTTS, etc.) fails
    in a way that isn't the caller's fault. Mapped to HTTP 502 below."""

    def __init__(self, service: str, detail: str):
        self.service = service
        self.detail = detail
        super().__init__(f"{service} error: {detail}")


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(UpstreamServiceError)
    async def upstream_error_handler(request: Request, exc: UpstreamServiceError):
        logger.error("Upstream service failure: %s — %s", exc.service, exc.detail)
        return JSONResponse(
            status_code=502,
            content={"detail": f"{exc.service} is currently unavailable. Please try again."},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "An unexpected error occurred. Please try again."},
        )
