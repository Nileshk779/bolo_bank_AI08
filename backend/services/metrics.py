"""
Operational metrics in Prometheus format, served at GET /metrics.

    bolobank_http_requests_total{method,route,status}     requests
    bolobank_http_request_seconds{method,route}           response time
    bolobank_ai_calls_total{model,outcome}                AI calls (ok / error)
    bolobank_ai_call_seconds{model}                       AI response time
    bolobank_ai_tokens_total{kind}                        tokens (prompt / completion)
    bolobank_cache_total{cache,result}                    answer / speech cache hits and misses
    bolobank_rate_limited_total{bucket}                   requests refused by rate limits

Routes are labelled by their template (/api/schemes/updates/{draft_id}), never
the raw URL, so labels stay few. /metrics is not under /api, so the web proxy
does not expose it publicly; set METRICS_TOKEN to also require a token.

Several processes in one container (uvicorn --workers N): set
PROMETHEUS_MULTIPROC_DIR to an empty writable directory so the numbers from
all processes are combined. One process per container needs nothing.
"""
import os
import time

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Histogram, generate_latest, multiprocess
from starlette.middleware.base import BaseHTTPMiddleware

from core.config import settings

_BUCKETS = (0.05, 0.1, 0.25, 0.5, 1, 2, 3, 5, 8, 13, 30)

HTTP_REQUESTS = Counter("bolobank_http_requests_total", "HTTP requests", ["method", "route", "status"])
HTTP_SECONDS = Histogram("bolobank_http_request_seconds", "HTTP response time", ["method", "route"], buckets=_BUCKETS)
AI_CALLS = Counter("bolobank_ai_calls_total", "AI (LLM) calls", ["model", "outcome"])
AI_SECONDS = Histogram("bolobank_ai_call_seconds", "AI (LLM) response time", ["model"], buckets=_BUCKETS)
AI_TOKENS = Counter("bolobank_ai_tokens_total", "AI tokens used", ["kind"])
CACHE = Counter("bolobank_cache_total", "Cache lookups", ["cache", "result"])
RATE_LIMITED = Counter("bolobank_rate_limited_total", "Requests refused by rate limits", ["bucket"])


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            route = request.scope.get("route")
            template = getattr(route, "path", None) or "unmatched"
            if template != "/metrics":
                HTTP_REQUESTS.labels(request.method, template, str(status)).inc()
                HTTP_SECONDS.labels(request.method, template).observe(time.perf_counter() - start)


router = APIRouter(tags=["monitoring"])


@router.get("/metrics", include_in_schema=False)
def metrics(authorization: str | None = Header(None)):
    if settings.METRICS_TOKEN and authorization != f"Bearer {settings.METRICS_TOKEN}":
        raise HTTPException(401, "Metrics token required")
    if os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
        return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
