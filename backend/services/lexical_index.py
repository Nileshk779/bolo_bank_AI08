"""
Keyword (lexical) matching used alongside semantic search — "hybrid search".

The multilingual embedding model is good at meaning but can blur topics
whose difference is a specific word ("PAN", "Jan Dhan", "cheque",
"nominee"). This index scores how many distinctive character n-grams a
query shares with each knowledge-base entry (title, keywords, content and
example questions), weighted by TF-IDF so common words count for little.

Character n-grams (not whole words) are used because they work the same
way for every script — Devanagari, Kannada, Telugu, Latin — and tolerate
inflection and spelling variation ("passbook"/"पासबुक"/"पासबुकची",
"khata"/"khaata"). Pure numpy; no extra dependency.
"""
import math
import re
from collections import Counter

import numpy as np

NGRAM_SIZES = (3, 4)
_SPLIT_RE = re.compile(r"[\s.,?!;:()'\"/\-–—।|]+")


def _ngrams(text: str) -> Counter:
    grams: Counter = Counter()
    for word in _SPLIT_RE.split(text.lower()):
        if not word:
            continue
        padded = f" {word} "
        for n in NGRAM_SIZES:
            if len(padded) >= n:
                grams.update(padded[i : i + n] for i in range(len(padded) - n + 1))
    return grams


class LexicalIndex:
    def __init__(self, doc_ids: list[str], texts: list[str]):
        self.doc_ids = doc_ids
        counts = [_ngrams(t) for t in texts]
        df: Counter = Counter()
        for c in counts:
            df.update(c.keys())
        n_docs = len(texts)
        self._vocab = {g: i for i, g in enumerate(df)}
        self._idf = np.array([math.log((1 + n_docs) / (1 + df[g])) + 1 for g in self._vocab], dtype="float32")
        self._matrix = np.vstack([self._vectorize(c) for c in counts]) if texts else np.zeros((0, len(self._vocab)), "float32")

    def _vectorize(self, counts: Counter) -> np.ndarray:
        v = np.zeros(len(self._vocab), dtype="float32")
        for g, tf in counts.items():
            i = self._vocab.get(g)
            if i is not None:
                v[i] = (1 + math.log(tf)) * self._idf[i]
        norm = np.linalg.norm(v)
        return v / norm if norm else v

    def scores(self, query: str) -> dict[str, float]:
        """Cosine similarity (0..1) between the query and every entry."""
        if not len(self.doc_ids):
            return {}
        sims = self._matrix @ self._vectorize(_ngrams(query))
        return {doc_id: float(s) for doc_id, s in zip(self.doc_ids, sims)}
