"""
Rate limiting — protects the AI quota and the login endpoint from abuse.

Limits are per customer session and per staff member first, and per client
IP only as a generous ceiling: all customers at a branch kiosk usually share
one IP address, so a strict per-IP limit would block a whole branch.

Sliding-window counters. With REDIS_URL set they live in Redis and are
shared by every server process; otherwise in this process's memory (with
several processes each would keep its own count). If Redis is unreachable
requests are allowed through (fail open) rather than blocked.
"""
import threading
import time
import uuid
from collections import deque

from fastapi import Depends, HTTPException, Request

from auth.security import get_current_customer, get_current_staff
from core.config import settings
from services import metrics, redis_client


class SlidingWindowLimiter:
    def __init__(self):
        self._hits: dict[str, deque] = {}
        self._lock = threading.Lock()
        self._calls = 0

    def hit(self, key: str, limit: int, window_seconds: float = 60.0) -> tuple[bool, int]:
        """Records one request for `key`. Returns (allowed, retry_after_seconds)."""
        now = time.monotonic()
        with self._lock:
            q = self._hits.setdefault(key, deque())
            while q and q[0] <= now - window_seconds:
                q.popleft()
            if len(q) >= limit:
                return False, max(1, int(q[0] + window_seconds - now) + 1)
            q.append(now)
            self._calls += 1
            if self._calls % 1000 == 0:
                self._sweep(now, window_seconds)
            return True, 0

    def _sweep(self, now: float, window_seconds: float) -> None:
        """Drops keys with no recent requests so memory stays bounded."""
        for key in [k for k, q in self._hits.items() if not q or q[-1] <= now - window_seconds]:
            del self._hits[key]

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


class RedisSlidingWindowLimiter:
    """Same interface, counters in a Redis sorted set per key (score = time)."""

    def __init__(self, client):
        self._r = client

    def hit(self, key: str, limit: int, window_seconds: float = 60.0) -> tuple[bool, int]:
        k = redis_client.key("rl", key)
        now = time.time()
        member = f"{now}:{uuid.uuid4().hex[:8]}"
        try:
            pipe = self._r.pipeline(transaction=True)
            pipe.zremrangebyscore(k, 0, now - window_seconds)
            pipe.zadd(k, {member: now})
            pipe.zcard(k)
            pipe.expire(k, int(window_seconds) + 1)
            count = pipe.execute()[2]
            if count <= limit:
                return True, 0
            self._r.zrem(k, member)  # a refused request doesn't count
            oldest = self._r.zrange(k, 0, 0, withscores=True)
            retry_after = int(oldest[0][1] + window_seconds - now) + 1 if oldest else int(window_seconds)
            return False, max(1, retry_after)
        except Exception as exc:  # Redis down: never block customers because of it
            redis_client.warn_unavailable(exc)
            return True, 0

    def reset(self) -> None:
        for k in self._r.scan_iter(match=redis_client.key("rl", "*")):
            self._r.delete(k)


def _build_limiter():
    client = redis_client.get_redis()
    return RedisSlidingWindowLimiter(client) if client is not None else SlidingWindowLimiter()


limiter = _build_limiter()


def client_ip(request: Request) -> str:
    if settings.TRUST_PROXY_HEADERS:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def enforce(*checks: tuple[str, int]) -> None:
    """Each check is (key, per-minute limit). Raises 429 on the first one exceeded."""
    if not settings.RATE_LIMIT_ENABLED:
        return
    for key, limit in checks:
        allowed, retry_after = limiter.hit(key, limit)
        if not allowed:
            metrics.RATE_LIMITED.labels(key.split(":", 1)[0]).inc()
            raise HTTPException(429, "Too many requests. Please wait a moment and try again.", headers={"Retry-After": str(retry_after)})


# --- FastAPI dependencies ------------------------------------------------ #
def limit_session_start(request: Request) -> None:
    enforce((f"start:ip:{client_ip(request)}", settings.RATE_LIMIT_SESSION_START_PER_MIN))


def limit_customer_ai(request: Request, customer: dict = Depends(get_current_customer)) -> None:
    enforce(
        (f"cust:{customer.get('sub')}", settings.RATE_LIMIT_CUSTOMER_AI_PER_MIN),
        (f"ai:ip:{client_ip(request)}", settings.RATE_LIMIT_IP_AI_PER_MIN),
    )


def limit_customer_speech(request: Request, customer: dict = Depends(get_current_customer)) -> None:
    # Text-to-speech is called for every screen of the eligibility checker,
    # so it gets its own, more generous bucket.
    enforce(
        (f"speak:{customer.get('sub')}", settings.RATE_LIMIT_CUSTOMER_SPEECH_PER_MIN),
        (f"ai:ip:{client_ip(request)}", settings.RATE_LIMIT_IP_AI_PER_MIN),
    )


def limit_staff_ai(request: Request, staff: str = Depends(get_current_staff)) -> None:
    enforce(
        (f"staff:{staff}", settings.RATE_LIMIT_STAFF_AI_PER_MIN),
        (f"ai:ip:{client_ip(request)}", settings.RATE_LIMIT_IP_AI_PER_MIN),
    )


def limit_public(request: Request) -> None:
    enforce((f"public:ip:{client_ip(request)}", settings.RATE_LIMIT_PUBLIC_PER_MIN))


def limit_login(request: Request, username: str | None = None) -> None:
    checks = [(f"login:ip:{client_ip(request)}", settings.RATE_LIMIT_LOGIN_PER_MIN)]
    if username:
        checks.append((f"login:user:{username.lower()}", settings.RATE_LIMIT_LOGIN_PER_USER_PER_MIN))
    enforce(*checks)
