"""Single-run background job lock (services/job_lock.py) and the audio upload limit."""
from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException

from database.session import SessionLocal
from services import job_lock
from services.speech_service import transcribe_upload, settings


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.close()


def test_only_one_process_gets_the_lock_until_it_expires(db):
    now = datetime(2040, 1, 1, 9, 0)
    assert job_lock.acquire(db, "test-job", 3600, now=now, owner="server-a")
    assert not job_lock.acquire(db, "test-job", 3600, now=now + timedelta(minutes=5), owner="server-b")
    assert not job_lock.acquire(db, "test-job", 3600, now=now + timedelta(minutes=59), owner="server-a")
    assert job_lock.acquire(db, "test-job", 3600, now=now + timedelta(hours=1, seconds=1), owner="server-b")


def test_locks_are_independent_per_job(db):
    now = datetime(2040, 2, 1)
    assert job_lock.acquire(db, "job-x", 60, now=now)
    assert job_lock.acquire(db, "job-y", 60, now=now)


class _Upload:
    filename = "speech.webm"

    def __init__(self, data):
        self._data = data

    async def read(self, size=-1):
        return self._data if size < 0 else self._data[:size]


@pytest.mark.asyncio
async def test_oversized_recording_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "MAX_AUDIO_UPLOAD_MB", 0.001)  # ~1 KB
    with pytest.raises(HTTPException) as exc:
        await transcribe_upload(_Upload(b"x" * 5000), "mr")
    assert exc.value.status_code == 413


@pytest.mark.asyncio
async def test_empty_recording_is_rejected():
    with pytest.raises(HTTPException) as exc:
        await transcribe_upload(_Upload(b""), "mr")
    assert exc.value.status_code == 400
