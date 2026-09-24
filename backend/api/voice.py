from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse

from auth.security import get_current_staff
from services.response_privacy_service import protect_for_speech
from services.speech_service import transcribe_upload
from services.tts_service import synthesize_speech

router = APIRouter(prefix="/api", tags=["voice"])


@router.post("/transcribe")
async def transcribe(
    audio: UploadFile = File(...),
    language: str = Form("hi"),
    staff: str = Depends(get_current_staff),
):
    text = await transcribe_upload(audio, language)
    return {"text": text}


@router.post("/speak")
async def speak(
    background_tasks: BackgroundTasks,
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

    The synthesized mp3 is deleted right after it's streamed to the client
    (via BackgroundTasks) — otherwise every reply would leave a permanent
    audio file on disk indefinitely, which is both a disk-space leak and an
    unnecessary retention of (admittedly already privacy-filtered) spoken
    content."""
    safe_text = protect_for_speech(text, language=language).safe_text
    filename = synthesize_speech(safe_text, language=language, slow=elderly_mode)
    background_tasks.add_task(lambda: filename.unlink(missing_ok=True))
    return FileResponse(filename, media_type="audio/mpeg", filename="reply.mp3", background=background_tasks)
