"""Structured logging setup — call setup_logging() once at startup (main.py
does this). Everywhere else, just use logging.getLogger(__name__)."""
import logging
import sys

from core.config import settings

_CONFIGURED = False


def setup_logging() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    root = logging.getLogger()
    root.setLevel(settings.LOG_LEVEL)
    root.handlers = [handler]

    # Quiet down noisy third-party loggers unless we're in DEBUG.
    if settings.LOG_LEVEL != "DEBUG":
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)

    _CONFIGURED = True

    if settings.using_default_secret:
        logging.getLogger("bolobank.config").warning(
            "SECRET_KEY is not set — using the insecure default. "
            "Set SECRET_KEY in your .env before any real deployment."
        )
