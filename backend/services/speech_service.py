"""Speech-to-text — wraps the Groq Whisper transcription call."""
import uuid
from pathlib import Path

from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool

from core.config import AUDIO_DIR, settings
from services.llm_service import transcribe_audio

# Client-supplied filenames are never trusted as part of a filesystem path
# (that's a path-traversal vector — a filename like "../../etc/cron.d/x" or
# an absolute path would otherwise let a caller write outside AUDIO_DIR).
# Only the extension is taken from it, and only if it's on this allowlist;
# everything else about the on-disk name is generated server-side.
_ALLOWED_AUDIO_EXTENSIONS = {".webm", ".wav", ".mp3", ".m4a", ".ogg", ".mp4", ".flac"}
_DEFAULT_EXTENSION = ".webm"  # what the browser's MediaRecorder produces


def _write_file(path: Path, data: bytes) -> None:
    with open(path, "wb") as f:
        f.write(data)


async def transcribe_upload(audio_file, language: str) -> str:
    """Writes the uploaded audio to a temp file, transcribes it, then
    always cleans up — same lifecycle as the original /api/transcribe."""
    ext = Path(audio_file.filename or "").suffix.lower()
    if ext not in _ALLOWED_AUDIO_EXTENSIONS:
        ext = _DEFAULT_EXTENSION

    tmp_path = AUDIO_DIR / f"{uuid.uuid4()}{ext}"
    # Read at most one byte past the limit, so an oversized upload is
    # rejected without ever holding the whole thing in memory.
    limit = int(settings.MAX_AUDIO_UPLOAD_MB * 1024 * 1024)
    data = await audio_file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f"Recording too large (limit {settings.MAX_AUDIO_UPLOAD_MB:g} MB)")
    if not data:
        raise HTTPException(400, "Empty recording")
    # The Whisper call blocks for a second or more; run it in a worker
    # thread so this async endpoint doesn't stall every other request.
    await run_in_threadpool(_write_file, tmp_path, data)
    try:
        return await run_in_threadpool(transcribe_audio, tmp_path, language)
    finally:
        tmp_path.unlink(missing_ok=True)
