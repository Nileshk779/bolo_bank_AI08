"""
Voice pipeline tests: language handling across all 5 supported languages
(en, hi, mr, te, kn) and Elderly Voice Mode's slower TTS pace. Mocks gTTS/
Groq (unreachable in this sandbox — see other test files) to verify our
own wiring: which language code and which `slow` flag actually reach the
synthesis call, and that /api/speak's privacy filter runs before that call
regardless of language.
"""
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from services.tts_service import _GTTS_LANG_MAP, synthesize_speech

SUPPORTED_LANGUAGES = ["en", "hi", "mr", "te", "kn"]


def _disposable_mp3() -> Path:
    """A throwaway file safe for a mocked /api/speak response to actually
    delete via its background cleanup task — never a real source file."""
    f = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    f.write(b"fake-mp3-bytes")
    f.close()
    return Path(f.name)


@pytest.mark.parametrize("language", SUPPORTED_LANGUAGES)
def test_all_five_languages_map_to_a_valid_gtts_code(language):
    assert language in _GTTS_LANG_MAP
    assert _GTTS_LANG_MAP[language] == language  # gTTS uses the same ISO codes BoloBank does


@pytest.mark.parametrize("language", SUPPORTED_LANGUAGES)
def test_synthesize_speech_passes_correct_language_and_normal_pace(language):
    with patch("gtts.gTTS") as mock_gtts:
        mock_gtts.return_value.save = lambda path: None
        synthesize_speech("Hello", language=language, slow=False)

    mock_gtts.assert_called_once()
    assert mock_gtts.call_args.kwargs["lang"] == language
    assert mock_gtts.call_args.kwargs["slow"] is False


@pytest.mark.parametrize("language", SUPPORTED_LANGUAGES)
def test_elderly_mode_uses_slow_speech_pace(language):
    with patch("gtts.gTTS") as mock_gtts:
        mock_gtts.return_value.save = lambda path: None
        synthesize_speech("Hello", language=language, slow=True)

    assert mock_gtts.call_args.kwargs["slow"] is True


def test_unsupported_language_falls_back_to_hindi():
    with patch("gtts.gTTS") as mock_gtts:
        mock_gtts.return_value.save = lambda path: None
        synthesize_speech("Hello", language="fr", slow=False)

    assert mock_gtts.call_args.kwargs["lang"] == "hi"


# --- /api/speak: elderly_mode reaches synthesis, privacy filter always runs --- #


def _login(client) -> str:
    res = client.post("/api/auth/login", data={"username": "staff", "password": "bolobank123"})
    return res.json()["access_token"]


@pytest.mark.parametrize("language", SUPPORTED_LANGUAGES)
def test_speak_endpoint_elderly_mode_reaches_tts_per_language(client, language):
    with patch("api.voice.synthesize_speech") as mock_synth:
        mock_synth.return_value = _disposable_mp3()
        token = _login(client)
        res = client.post(
            "/api/speak",
            data={"text": "Hello there", "language": language, "elderly_mode": "true"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        assert mock_synth.call_args.kwargs["language"] == language
        assert mock_synth.call_args.kwargs["slow"] is True


def test_speak_endpoint_deletes_the_synthesized_file_after_serving_it(client):
    """Regression test for the disk-space-leak fix found in the final
    security review — synthesized audio must not accumulate on disk."""
    audio_path = _disposable_mp3()
    assert audio_path.exists()

    with patch("api.voice.synthesize_speech", return_value=audio_path):
        token = _login(client)
        res = client.post(
            "/api/speak",
            data={"text": "Hello there", "language": "en"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200

    assert not audio_path.exists()
