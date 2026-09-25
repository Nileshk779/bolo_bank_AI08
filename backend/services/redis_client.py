"""
Shared Redis connection (optional).

With REDIS_URL set, rate-limit counters, the answer cache and the speech
cache are shared by every server process. Without it, each process keeps
its own in memory (fine for one process / local development).

Redis is treated as an optimisation, never a hard dependency: if it is
unreachable, rate limits let requests through and caches behave as empty,
and a warning is logged — customers never see an error because of it.
"""
import logging
import threading
import time

from core.config import settings

logger = logging.getLogger("bolobank.redis")

_client = None
_lock = threading.Lock()
_last_warning = 0.0


def get_redis():
    """The shared client, or None when REDIS_URL is not configured."""
    global _client
    if not settings.REDIS_URL:
        return None
    if _client is None:
        with _lock:
            if _client is None:
                import redis

                _client = redis.Redis.from_url(settings.REDIS_URL, socket_timeout=2, socket_connect_timeout=2,
                                               health_check_interval=30)
    return _client


def key(*parts: str) -> str:
    return settings.REDIS_PREFIX + ":".join(parts)


def warn_unavailable(exc: Exception) -> None:
    """Logs at most once a minute, so an outage doesn't flood the logs."""
    global _last_warning
    now = time.monotonic()
    if now - _last_warning > 60:
        _last_warning = now
        logger.warning("Redis unavailable, continuing without it: %s", exc)
