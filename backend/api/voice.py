from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import Response

from auth.security import get_current_staff
from services.response_privacy_service import protect_for_speech
from services.rate_limit import limit_staff_ai
from services.speech_service import transcribe_upload
from services.tts_service import cached_speech, synthesize_speech

router = APIRouter(prefix="/api", tags=["voice"])


@router.post("/transcribe", dependencies=[Depends(limit_staff_ai)])
async def transcribe(
    audio: UploadFile = File(...),
    language: str = Form("hi"),
    staff: str = Depends(get_current_staff),
):
    text = await transcribe_upload(audio, language)
    return {"text": text}


@router.post("/speak", dependencies=[Depends(limit_staff_ai)])
def speak(
    text: str = Form(...),
    language: str = Form("hi"),
    elderly_mode: bool = Form(False),
    staff: str = Depends(get_current_staff),
):
    """Text to speech. This is the single, unconditional enforcement point
    of the Response Privacy Layer: EVERY call runs the text through
    protect_for_speech() before it reaches gTTS — there is no bypass flag,
    because "sensitive values must not enter the TTS pipeline" is an
    absolute rule, not a best-effort one that depends on the caller
    remembering to pre-sanitize. In the normal flow the text is already
    safe (chat/copilot already return a privacy-safe `spoken_response`), so
    this is nearly always a no-op — but it's the guarantee, not a
    convenience.

    elderly_mode=True uses a slower, clearer speaking pace (Elderly Voice
    Mode).

    The synthesized mp3 file is deleted as soon as it has been read
    (services/tts_service.cached_speech) — no audio accumulates on disk. The
    audio bytes of the (already privacy-filtered) text are kept in a small
    in-memory cache so repeated sentences aren't synthesized again."""
    safe_text = protect_for_speech(text, language=language).safe_text
    audio = cached_speech(safe_text, language, elderly_mode, synthesize_speech)
    return Response(audio, media_type="audio/mpeg", headers={"Content-Disposition": 'inline; filename="reply.mp3"'})
