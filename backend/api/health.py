from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from database.session import engine
from services import redis_client

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health():
    """Liveness: the process is up."""
    return {"status": "ok"}


@router.get("/health/ready")
def ready():
    """Readiness: the database (and Redis, when configured) can be reached.
    A load balancer should only send traffic to servers that return 200."""
    checks = {}
    try:
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {type(exc).__name__}"
    r = redis_client.get_redis()
    if r is not None:
        try:
            r.ping()
            checks["redis"] = "ok"
        except Exception as exc:
            checks["redis"] = f"error: {type(exc).__name__}"
    ok = all(v == "ok" for v in checks.values())
    return JSONResponse({"status": "ready" if ok else "not ready", "checks": checks}, status_code=200 if ok else 503)
