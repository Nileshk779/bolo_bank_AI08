"""Answer cache (services/answer_cache.py) and speech cache (services/tts_service.py)."""
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from services import ai_orchestrator as orch_module
from services.ai_orchestrator import ai_orchestrator
from services.answer_cache import AnswerCache, answer_cache, is_cacheable
from services.tts_service import cached_speech, clear_speech_cache

settings = orch_module.settings


def _unit(seed):
    v = np.random.default_rng(seed).normal(size=384)
    return (v / np.linalg.norm(v)).astype("float32")


def _near(v, seed, weight=0.995):
    w = weight * v + (1 - weight) * _unit(seed)
    return (w / np.linalg.norm(w)).astype("float32")


@pytest.fixture
def cache_on(monkeypatch):
    monkeypatch.setattr(settings, "ANSWER_CACHE_ENABLED", True)
    monkeypatch.setattr(settings, "TTS_CACHE_ENABLED", True)
    answer_cache.clear()
    clear_speech_cache()
    yield
    answer_cache.clear()
    clear_speech_cache()


# ------------------------------------------------------------ unit level --- #
def test_privacy_rule_for_what_may_be_cached():
    assert is_cacheable("what time does the bank open")
    assert not is_cacheable("my account 1234 is blocked")  # digits
    assert not is_cacheable(" ".join(["word"] * 26))  # long, personal stories
    assert not is_cacheable("")


def test_cache_matches_only_near_identical_meaning_in_the_same_bucket():
    c = AnswerCache()
    v = _unit(1)
    bucket = ("mr", "simple", "", (("KB043", 0),))
    c.put(bucket, v, "answer")
    assert c.get(bucket, _near(v, 2)) == "answer"                       # same meaning
    assert c.get(bucket, _unit(3)) is None                              # different meaning
    assert c.get(("hi",) + bucket[1:], v) is None                        # other language
    assert c.get(bucket[:3] + ((("KB019", 0),),), v) is None             # other policy text


def test_expired_and_overflowing_entries_are_dropped(monkeypatch):
    c = AnswerCache()
    monkeypatch.setattr(settings, "ANSWER_CACHE_MAX_ENTRIES", 2)
    for i in range(3):
        c.put(("b",), _unit(10 + i), f"a{i}")
    assert len(c) == 2 and c.get(("b",), _unit(10)) is None  # oldest evicted
    monkeypatch.setattr(settings, "ANSWER_CACHE_TTL_SECONDS", -1)
    assert c.get(("b",), _unit(11)) is None and len(c) == 0


# ------------------------------------------------- orchestrator integration --- #
def _grounded(_q):
    return {"grounded": True, "context": "[Source: Branch Hours]", "confidence": 0.8,
            "sources": [{"topic": "Branch Working Hours and Holidays", "doc_id": "KB043", "chunk_index": 0, "score": 0.8}]}


def test_equivalent_questions_call_the_ai_once(cache_on):
    base = _unit(42)
    vectors = {"bank kab khulta hai": base, "bank kab khulti hai": _near(base, 43)}
    with patch.object(orch_module, "_run_retrieval", side_effect=_grounded), \
         patch.object(orch_module.embedding_service, "embed", side_effect=lambda texts: np.vstack([vectors[t] for t in texts])), \
         patch.object(orch_module, "chat_completion", return_value="10 बजे\nEN: 10 am") as llm:
        a = ai_orchestrator.handle_customer_query("bank kab khulta hai", "hi", "simple")
        b = ai_orchestrator.handle_customer_query("bank kab khulti hai", "hi", "simple")
        c = ai_orchestrator.handle_customer_query("bank kab khulta hai", "hi", "detailed")  # other level -> new answer
    assert llm.call_count == 2
    assert a["reply_local"] == b["reply_local"] == "10 बजे"
    assert c["reply_local"] == "10 बजे"


def test_questions_with_numbers_are_never_cached(cache_on):
    with patch.object(orch_module, "_run_retrieval", side_effect=_grounded), \
         patch.object(orch_module.embedding_service, "embed", return_value=np.vstack([_unit(5)])), \
         patch.object(orch_module, "chat_completion", return_value="x\nEN: x") as llm:
        ai_orchestrator.handle_customer_query("is branch 2 open", "en", "simple")
        ai_orchestrator.handle_customer_query("is branch 2 open", "en", "simple")
    assert llm.call_count == 2


# ------------------------------------------------------------ speech cache --- #
def _mp3(content=b"ID3fake"):
    f = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    f.write(content)
    f.close()
    return Path(f.name)


def test_same_sentence_is_synthesized_once_and_files_are_deleted(cache_on):
    made = []

    def synth(text, language, slow):
        made.append(_mp3())
        return made[-1]

    assert cached_speech("नमस्कार", "mr", True, synth) == b"ID3fake"
    assert cached_speech("नमस्कार", "mr", True, synth) == b"ID3fake"
    cached_speech("नमस्कार", "mr", False, synth)  # normal pace is a different clip
    assert len(made) == 2
    assert not any(p.exists() for p in made)


def test_speech_cache_can_be_disabled(monkeypatch):
    monkeypatch.setattr(settings, "TTS_CACHE_ENABLED", False)
    synth = MagicMock(side_effect=lambda *a, **k: _mp3())
    cached_speech("hello", "en", False, synth)
    cached_speech("hello", "en", False, synth)
    assert synth.call_count == 2


def test_customer_speak_endpoint_serves_cached_audio(client, cache_on):
    s = client.post("/api/customer/session/start", json={"language": "mr"}).json()
    headers = {"Authorization": f"Bearer {s['customer_token']}"}
    with patch("api.customer.synthesize_speech", side_effect=lambda *a, **k: _mp3(b"ID3clip")) as synth:
        r1 = client.post("/api/customer/speak", headers=headers, data={"text": "तुमच्याकडे काय आहे?", "language": "mr"})
        r2 = client.post("/api/customer/speak", headers=headers, data={"text": "तुमच्याकडे काय आहे?", "language": "mr"})
    assert r1.status_code == r2.status_code == 200
    assert r1.content == r2.content == b"ID3clip" and r1.headers["content-type"] == "audio/mpeg"
    assert synth.call_count == 1
