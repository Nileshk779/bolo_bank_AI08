"""
Security regression tests found during the final review pass.
"""
import io
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from core.config import AUDIO_DIR
from services.speech_service import transcribe_upload


class _FakeUploadFile:
    def __init__(self, filename: str, content: bytes = b"fake-audio-bytes"):
        self.filename = filename
        self._content = content

    async def read(self):
        return self._content


@pytest.mark.asyncio
async def test_malicious_filename_cannot_escape_audio_dir():
    """A client-supplied filename like '../../../etc/cron.d/evil' must never
    become part of the on-disk path — regression test for the path-
    traversal issue found in the final security review."""
    malicious = _FakeUploadFile(filename="../../../../tmp/evil_traversal_test.webm")

    written_paths = []
    real_open = open

    def _spy_open(path, *args, **kwargs):
        written_paths.append(str(path))
        return real_open(path, *args, **kwargs)

    with patch("services.speech_service.transcribe_audio", return_value="ok"):
        with patch("builtins.open", side_effect=_spy_open):
            await transcribe_upload(malicious, "en")

    assert len(written_paths) == 1
    written_path = Path(written_paths[0]).resolve()
    # The actual write must land inside AUDIO_DIR, nowhere else.
    assert written_path.parent == AUDIO_DIR.resolve()
    assert "evil_traversal_test" not in written_path.name
    assert not (Path("/tmp") / "evil_traversal_test.webm").exists()


@pytest.mark.asyncio
async def test_disallowed_extension_falls_back_to_default():
    upload = _FakeUploadFile(filename="malware.exe")
    with patch("services.speech_service.transcribe_audio", return_value="ok") as mock_transcribe:
        await transcribe_upload(upload, "en")
    used_path = mock_transcribe.call_args.args[0]
    assert used_path.suffix == ".webm"


@pytest.mark.asyncio
async def test_allowed_extension_is_preserved():
    upload = _FakeUploadFile(filename="recording.wav")
    with patch("services.speech_service.transcribe_audio", return_value="ok") as mock_transcribe:
        await transcribe_upload(upload, "en")
    used_path = mock_transcribe.call_args.args[0]
    assert used_path.suffix == ".wav"


@pytest.mark.asyncio
async def test_temp_file_is_always_cleaned_up_even_on_failure():
    upload = _FakeUploadFile(filename="recording.webm")
    with patch("services.speech_service.transcribe_audio", side_effect=RuntimeError("boom")):
        with pytest.raises(RuntimeError):
            await transcribe_upload(upload, "en")
    # No leftover files in AUDIO_DIR from this test.
    leftover = list(AUDIO_DIR.glob("*.webm"))
    assert leftover == []


def test_tts_cleans_up_partial_file_on_synthesis_failure():
    """Regression test for the disk-hygiene issue found in the final
    security review: a failed gTTS call could leave a 0-byte orphan file
    behind in AUDIO_DIR indefinitely."""
    from core.exceptions import UpstreamServiceError
    from services.tts_service import synthesize_speech

    def _failing_gtts(*args, **kwargs):
        raise RuntimeError("simulated network failure")

    with patch("gtts.gTTS", side_effect=_failing_gtts):
        before = set(AUDIO_DIR.glob("*.mp3"))
        with pytest.raises(UpstreamServiceError):
            synthesize_speech("Hello", language="en")
        after = set(AUDIO_DIR.glob("*.mp3"))

    assert after == before  # no new file left behind
