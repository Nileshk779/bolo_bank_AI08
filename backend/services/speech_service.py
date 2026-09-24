"""Speech-to-text — wraps the Groq Whisper transcription call."""
import uuid
from pathlib import Path

from core.config import AUDIO_DIR
from services.llm_service import transcribe_audio

# Client-supplied filenames are never trusted as part of a filesystem path
# (that's a path-traversal vector — a filename like "../../etc/cron.d/x" or
# an absolute path would otherwise let a caller write outside AUDIO_DIR).
# Only the extension is taken from it, and only if it's on this allowlist;
# everything else about the on-disk name is generated server-side.
_ALLOWED_AUDIO_EXTENSIONS = {".webm", ".wav", ".mp3", ".m4a", ".ogg", ".mp4", ".flac"}
_DEFAULT_EXTENSION = ".webm"  # what the browser's MediaRecorder produces


async def transcribe_upload(audio_file, language: str) -> str:
    """Writes the uploaded audio to a temp file, transcribes it, then
    always cleans up — same lifecycle as the original /api/transcribe."""
    ext = Path(audio_file.filename or "").suffix.lower()
    if ext not in _ALLOWED_AUDIO_EXTENSIONS:
        ext = _DEFAULT_EXTENSION

    tmp_path = AUDIO_DIR / f"{uuid.uuid4()}{ext}"
    with open(tmp_path, "wb") as f:
        f.write(await audio_file.read())

    try:
        return transcribe_audio(tmp_path, language)
    finally:
        tmp_path.unlink(missing_ok=True)
