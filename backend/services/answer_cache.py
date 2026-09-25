"""
Answer cache — reuse an AI answer when a new question means the same thing.

Many customers ask the same things ("bank hours", "lost passbook"). A cached
answer is returned when ALL of these match a recent entry:
  * the same language, explanation level and follow-up type ("simpler" /
    "more detail"),
  * the same knowledge-base passages were retrieved (so the answer is based
    on the same policy text), and
  * the question's meaning is nearly identical: embedding cosine similarity
    >= ANSWER_CACHE_SIMILARITY (0.97 by default — deliberately strict).

Privacy: questions containing any digit, or longer than 25 words, are never
cached — they are the ones likely to carry personal details (amounts,
account/phone numbers, a customer's own story). Only policy answers grounded
in the knowledge base are cached; account-data answers never reach this.

With REDIS_URL set the cache is shared by every server process (RedisAnswerCache);
otherwise it is in this process's memory. Both have a time limit and a size
limit, and a Redis outage just means cache misses.
"""
import base64
import hashlib
import json
import re
import threading
import time
from collections import OrderedDict

import numpy as np

from core.config import settings
from services import redis_client

_DIGIT = re.compile(r"\d")


def is_cacheable(question: str) -> bool:
    return bool(question) and not _DIGIT.search(question) and len(question.split()) <= 25


class AnswerCache:
    def __init__(self):
        self._entries: OrderedDict[int, tuple] = OrderedDict()  # id -> (bucket, vector, answer, created)
        self._next_id = 0
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def get(self, bucket: tuple, vector: np.ndarray) -> str | None:
        now = time.monotonic()
        with self._lock:
            best_id, best_score = None, settings.ANSWER_CACHE_SIMILARITY
            for entry_id, (b, v, _answer, created) in list(self._entries.items()):
                if now - created > settings.ANSWER_CACHE_TTL_SECONDS:
                    del self._entries[entry_id]
                    continue
                if b == bucket:
                    score = float(np.dot(v, vector))
                    if score >= best_score:
                        best_id, best_score = entry_id, score
            if best_id is None:
                self.misses += 1
                return None
            self._entries.move_to_end(best_id)  # recently used
            self.hits += 1
            return self._entries[best_id][2]

    def put(self, bucket: tuple, vector: np.ndarray, answer: str) -> None:
        with self._lock:
            self._entries[self._next_id] = (bucket, vector, answer, time.monotonic())
            self._next_id += 1
            while len(self._entries) > settings.ANSWER_CACHE_MAX_ENTRIES:
                self._entries.popitem(last=False)  # least recently used

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self.hits = self.misses = 0

    def __len__(self) -> int:
        return len(self._entries)


class RedisAnswerCache:
    """Same interface as AnswerCache. One Redis list per bucket (newest
    first, capped at ANSWER_CACHE_PER_BUCKET); buckets are narrow (language,
    level, follow-up, retrieved passages), so each lookup scans a short list."""

    def __init__(self, client):
        self._r = client
        self.hits = 0
        self.misses = 0

    def _key(self, bucket: tuple) -> str:
        return redis_client.key("ac", hashlib.sha1(json.dumps(bucket, ensure_ascii=False).encode("utf-8")).hexdigest())

    def get(self, bucket: tuple, vector: np.ndarray) -> str | None:
        now = time.time()
        try:
            raw_entries = self._r.lrange(self._key(bucket), 0, settings.ANSWER_CACHE_PER_BUCKET - 1)
        except Exception as exc:
            redis_client.warn_unavailable(exc)
            return None
        best, best_score = None, settings.ANSWER_CACHE_SIMILARITY
        for raw in raw_entries:
            e = json.loads(raw)
            if now - e["t"] > settings.ANSWER_CACHE_TTL_SECONDS:
                continue
            v = np.frombuffer(base64.b64decode(e["v"]), dtype="float32")
            score = float(np.dot(v, vector))
            if score >= best_score:
                best, best_score = e["a"], score
        if best is None:
            self.misses += 1
        else:
            self.hits += 1
        return best

    def put(self, bucket: tuple, vector: np.ndarray, answer: str) -> None:
        entry = json.dumps({"v": base64.b64encode(np.asarray(vector, dtype="float32").tobytes()).decode("ascii"),
                            "a": answer, "t": time.time()}, ensure_ascii=False)
        k = self._key(bucket)
        try:
            pipe = self._r.pipeline(transaction=True)
            pipe.lpush(k, entry)
            pipe.ltrim(k, 0, settings.ANSWER_CACHE_PER_BUCKET - 1)
            pipe.expire(k, settings.ANSWER_CACHE_TTL_SECONDS)
            pipe.execute()
        except Exception as exc:
            redis_client.warn_unavailable(exc)

    def clear(self) -> None:
        for k in self._r.scan_iter(match=redis_client.key("ac", "*")):
            self._r.delete(k)
        self.hits = self.misses = 0

    def __len__(self) -> int:
        return sum(self._r.llen(k) for k in self._r.scan_iter(match=redis_client.key("ac", "*")))


def _build_cache():
    client = redis_client.get_redis()
    return RedisAnswerCache(client) if client is not None else AnswerCache()


answer_cache = _build_cache()
