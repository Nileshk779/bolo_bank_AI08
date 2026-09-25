"""
Concurrency: slow AI calls must not make other requests wait.

The chat/voice/Copilot endpoints call blocking services (Groq, Whisper,
gTTS, the embedding model). If such an endpoint is declared `async def`,
the blocking call runs on the event loop and the whole server process
handles one request at a time. These tests fire requests concurrently with
the AI replaced by a 0.4 s sleep and check they overlap.
"""
import asyncio
import time
from unittest.mock import patch

import httpx
import pytest

from auth.security import create_access_token
from main import app

AI_SECONDS = 0.4
N = 8


def _slow_customer_answer(*args, **kwargs):
    time.sleep(AI_SECONDS)
    return {"reply_local": "x", "reply_english": "x", "spoken_response": "x", "sources": [], "confidence": 0.9, "grounded": True}


def _slow_employee_answer(*args, **kwargs):
    time.sleep(AI_SECONDS)
    return {"understood_summary": "s", "relevant_info": "i", "suggested_action": "a", "suggested_reply_local": "r",
            "suggested_reply_english": "r", "spoken_response": "r", "sources": [], "grounded": True}


async def _timed(requests) -> float:
    start = time.perf_counter()
    responses = await asyncio.gather(*requests)
    elapsed = time.perf_counter() - start
    assert all(r.status_code == 200 for r in responses), [r.status_code for r in responses]
    return elapsed


@pytest.mark.asyncio
async def test_customer_chat_requests_run_in_parallel():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        sessions = [(await client.post("/api/customer/session/start", json={"language": "mr"})).json() for _ in range(N)]
        with patch("api.customer.ai_orchestrator.handle_customer_query", side_effect=_slow_customer_answer):
            elapsed = await _timed([
                client.post("/api/customer/chat", headers={"Authorization": f"Bearer {s['customer_token']}"},
                            json={"session_id": s["session_id"], "text": "bank hours?", "language": "mr"})
                for s in sessions
            ])
    # One at a time would take N * 0.4 = 3.2 s.
    assert elapsed < AI_SECONDS * N / 2, f"{N} requests took {elapsed:.2f}s — they are running one at a time"


@pytest.mark.asyncio
async def test_copilot_requests_run_in_parallel():
    headers = {"Authorization": f"Bearer {create_access_token('staff')}"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        with patch("api.copilot.ai_orchestrator.handle_employee_query", side_effect=_slow_employee_answer):
            elapsed = await _timed([
                client.post("/api/copilot", headers=headers, json={"query": f"question {i}", "language": "hi"}) for i in range(N)
            ])
    assert elapsed < AI_SECONDS * N / 2, f"{N} requests took {elapsed:.2f}s — they are running one at a time"
