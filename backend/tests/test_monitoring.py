"""Metrics endpoint, readiness check and JSON logs."""
import json
import logging
from unittest.mock import MagicMock, patch

from services import metrics, redis_client


def test_metrics_endpoint_reports_requests_by_route_template(client):
    client.get("/api/health")
    client.get("/api/schemes/updates/12345/does-not-exist")
    body = client.get("/metrics").text
    assert 'bolobank_http_requests_total{method="GET",route="/api/health",status="200"}' in body
    assert "bolobank_http_request_seconds_bucket" in body
    assert "/12345/" not in body  # raw URLs never become labels


def test_metrics_token(client, monkeypatch):
    monkeypatch.setattr(metrics.settings, "METRICS_TOKEN", "s3cret")
    assert client.get("/metrics").status_code == 401
    assert client.get("/metrics", headers={"Authorization": "Bearer s3cret"}).status_code == 200


def test_ai_and_cache_counters_are_exposed(client):
    before = metrics.AI_CALLS.labels("m", "error")._value.get()
    metrics.AI_CALLS.labels("m", "error").inc()
    metrics.CACHE.labels("answer", "hit").inc()
    body = client.get("/metrics").text
    assert metrics.AI_CALLS.labels("m", "error")._value.get() == before + 1
    assert 'bolobank_cache_total{cache="answer",result="hit"}' in body


def test_readiness_checks_database_and_redis(client, monkeypatch):
    r = client.get("/api/health/ready")
    assert r.status_code == 200 and r.json()["checks"] == {"database": "ok"}  # no Redis configured
    broken = MagicMock(ping=MagicMock(side_effect=ConnectionError("down")))
    monkeypatch.setattr(redis_client, "get_redis", lambda: broken)
    r = client.get("/api/health/ready")
    assert r.status_code == 503 and r.json()["checks"]["redis"].startswith("error")


def test_json_log_format():
    from core.logging import _JsonFormatter

    record = logging.LogRecord("bolobank.test", logging.WARNING, __file__, 1, "Scheme %s approved", ("KCC",), None)
    entry = json.loads(_JsonFormatter().format(record))
    assert entry["level"] == "WARNING" and entry["message"] == "Scheme KCC approved" and entry["logger"] == "bolobank.test"
