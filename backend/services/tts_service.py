"""
Text-to-speech — wraps gTTS. Adds an elderly-mode slow/clear speaking pace
and, as of this feature, is always called downstream of the Response
Privacy Layer (see api/voice.py) — this module itself has no privacy logic
and just speaks whatever text it's given, by design (that's a separate
concern owned by response_privacy_service.py).
"""
import hashlib
import logging
import threading
import uuid
from collections import OrderedDict

from core.config import AUDIO_DIR, settings
from services import metrics, redis_client
from core.exceptions import UpstreamServiceError

logger = logging.getLogger("bolobank.tts")

_GTTS_LANG_MAP = {"hi": "hi", "mr": "mr", "te": "te", "kn": "kn", "en": "en"}


def synthesize_speech(text: str, language: str = "hi", slow: bool = False):
    """Writes an mp3 to AUDIO_DIR and returns its path. `slow=True` is used
    for Elderly Voice Mode — a slower, clearer speaking pace for customers
    who find rapid speech hard to follow."""
    from gtts import gTTS

    lang = _GTTS_LANG_MAP.get(language, "hi")
    filename = AUDIO_DIR / f"{uuid.uuid4()}.mp3"
    try:
        tts = gTTS(text=text, lang=lang, slow=slow)
        tts.save(str(filename))
    except Exception as exc:
        logger.error("gTTS synthesis failed: %s", exc)
        filename.unlink(missing_ok=True)  # gTTS can leave a partial/empty file behind on failure
        raise UpstreamServiceError("gTTS", str(exc)) from exc

    return filename


# --- Speech cache ----------------------------------------------------------
# The same sentences are spoken again and again (every eligibility-checker
# question, common answers), so each clip is generated once and reused. Only
# already privacy-filtered text reaches here. Shared in Redis when REDIS_URL
# is set (kept TTS_CACHE_TTL_SECONDS), otherwise in this process's memory.
_audio_cache: OrderedDict[str, bytes] = OrderedDict()
_audio_lock = threading.Lock()


def cached_speech(text: str, language: str, slow: bool, synthesize) -> bytes:
    """Returns mp3 bytes for `text`, from the cache or by calling
    `synthesize(text, language=..., slow=...)` (which returns a file path; the
    file is always deleted after reading). `synthesize` is passed in so the
    caller's own reference is used (and can be replaced in tests)."""
    key = hashlib.sha256(f"{language}|{int(slow)}|{text}".encode("utf-8")).hexdigest()
    r = redis_client.get_redis() if settings.TTS_CACHE_ENABLED else None
    if settings.TTS_CACHE_ENABLED:
        cached = _redis_get(r, key) if r is not None else _memory_get(key)
        metrics.CACHE.labels("speech", "hit" if cached is not None else "miss").inc()
        if cached is not None:
            return cached
    path = synthesize(text, language=language, slow=slow)
    try:
        audio = path.read_bytes()
    finally:
        path.unlink(missing_ok=True)
    if settings.TTS_CACHE_ENABLED:
        if r is not None:
            _redis_set(r, key, audio)
        else:
            _memory_set(key, audio)
    return audio


def _memory_get(key: str) -> bytes | None:
    with _audio_lock:
        if key in _audio_cache:
            _audio_cache.move_to_end(key)
            return _audio_cache[key]
    return None


def _memory_set(key: str, audio: bytes) -> None:
    with _audio_lock:
        _audio_cache[key] = audio
        while len(_audio_cache) > settings.TTS_CACHE_MAX_ENTRIES:
            _audio_cache.popitem(last=False)


def _redis_get(r, key: str) -> bytes | None:
    try:
        return r.get(redis_client.key("tts", key))
    except Exception as exc:
        redis_client.warn_unavailable(exc)
        return None


def _redis_set(r, key: str, audio: bytes) -> None:
    try:
        r.setex(redis_client.key("tts", key), settings.TTS_CACHE_TTL_SECONDS, audio)
    except Exception as exc:
        redis_client.warn_unavailable(exc)


def clear_speech_cache() -> None:
    with _audio_lock:
        _audio_cache.clear()
