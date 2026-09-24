"""
Text-to-speech — wraps gTTS. Adds an elderly-mode slow/clear speaking pace
and, as of this feature, is always called downstream of the Response
Privacy Layer (see api/voice.py) — this module itself has no privacy logic
and just speaks whatever text it's given, by design (that's a separate
concern owned by response_privacy_service.py).
"""
import logging
import uuid

from core.config import AUDIO_DIR
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
