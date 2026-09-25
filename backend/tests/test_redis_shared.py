"""
Redis-backed rate limits and caches (services/redis_client.py and friends).

fakeredis stands in for Redis. Two clients on one fake server behave like
two server processes sharing the same Redis.
"""
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import fakeredis
import numpy as np
import pytest

from services import redis_client, tts_service
from services.answer_cache import RedisAnswerCache
from services.rate_limit import RedisSlidingWindowLimiter, settings


@pytest.fixture
def server():
    return fakeredis.FakeServer()


def _client(server):
    return fakeredis.FakeRedis(server=server)


def _unit(seed):
    v = np.random.default_rng(seed).normal(size=384)
    return (v / np.linalg.norm(v)).astype("float32")


def test_rate_limit_is_shared_by_all_server_processes(server):
    process_a = RedisSlidingWindowLimiter(_client(server))
    process_b = RedisSlidingWindowLimiter(_client(server))
    assert process_a.hit("cust:s1", 3)[0]
    assert process_b.hit("cust:s1", 3)[0]
    assert process_a.hit("cust:s1", 3)[0]
    allowed, retry_after = process_b.hit("cust:s1", 3)  # 4th request, whichever process gets it
    assert not allowed and 1 <= retry_after <= 61
    assert process_b.hit("cust:s2", 3)[0]  # other customers unaffected


def test_refused_requests_do_not_count(server):
    lim = RedisSlidingWindowLimiter(_client(server))
    for _ in range(2):
        lim.hit("k", 2)
    for _ in range(5):
        assert not lim.hit("k", 2)[0]
    assert _client(server).zcard(redis_client.key("rl", "k")) == 2


def test_redis_outage_lets_customers_through():
    broken = MagicMock()
    broken.pipeline.side_effect = ConnectionError("redis down")
    assert RedisSlidingWindowLimiter(broken).hit("k", 1) == (True, 0)
    cache = RedisAnswerCache(MagicMock(lrange=MagicMock(side_effect=ConnectionError("down"))))
    assert cache.get(("b",), _unit(1)) is None  # just a miss


def test_answer_cache_is_shared_by_all_server_processes(server):
    a, b = RedisAnswerCache(_client(server)), RedisAnswerCache(_client(server))
    bucket = ("mr", "simple", "", (("KB043", 0),))
    v = _unit(7)
    a.put(bucket, v, "बँक सकाळी १० वाजता उघडते")
    assert b.get(bucket, v) == "बँक सकाळी १० वाजता उघडते"  # written by A, read by B
    assert b.get(bucket, _unit(8)) is None  # different meaning
    assert b.get(("hi",) + bucket[1:], v) is None  # different language


def test_answer_cache_limits(server, monkeypatch):
    c = RedisAnswerCache(_client(server))
    monkeypatch.setattr(settings, "ANSWER_CACHE_PER_BUCKET", 2)
    for i in range(4):
        c.put(("b",), _unit(20 + i), f"a{i}")
    assert len(c) == 2 and c.get(("b",), _unit(20)) is None  # oldest trimmed
    monkeypatch.setattr(settings, "ANSWER_CACHE_TTL_SECONDS", -1)
    assert c.get(("b",), _unit(23)) is None  # expired


def test_speech_cache_is_shared_via_redis(server, monkeypatch):
    monkeypatch.setattr(settings, "TTS_CACHE_ENABLED", True)
    monkeypatch.setattr(redis_client, "get_redis", lambda: _client(server))

    def synth(text, language, slow):
        f = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        f.write(b"ID3shared")
        f.close()
        return Path(f.name)

    synth_mock = MagicMock(side_effect=synth)
    assert tts_service.cached_speech("नमस्कार", "mr", True, synth_mock) == b"ID3shared"
    assert tts_service.cached_speech("नमस्कार", "mr", True, synth_mock) == b"ID3shared"
    assert synth_mock.call_count == 1
    assert _client(server).ttl(next(_client(server).scan_iter(match=redis_client.key("tts", "*")))) > 0
