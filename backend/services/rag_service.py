"""
Semantic retrieval over the bank policy knowledge base.

Pipeline: query -> query embedding -> cosine similarity search over
pre-embedded knowledge-base chunks -> top-K -> confidence check -> context
string (with source metadata) handed to the LLM. Replaces the previous
keyword-overlap implementation (raw word-set intersection, no real
understanding of meaning or paraphrase).

Grounding / anti-hallucination: `is_confident()` is a hard, programmatic
gate — if the best-matching chunk's similarity score is below
MIN_CONFIDENCE, the caller (ai_orchestrator / copilot_service) skips the
LLM call entirely and returns GROUNDING_FALLBACK directly. This is
deliberately not left to prompt instructions alone ("say you don't know if
you're not sure") — LLMs are unreliable at self-restraint, so the fallback
here is decided by code, not by asking the model to police itself. The
system prompt still carries a softer version of the same instruction as a
second layer of defense for cases that pass the confidence gate but are
still a partial/tangential match.

Paraphrase handling: each knowledge-base entry can list example
"questions" — the same question asked different ways, casually, and in
each supported language. They are embedded alongside the answer text and
point back to it, because a customer's question is usually far closer in
meaning to another phrasing of the question than to the answer's wording.
A hit on an example question returns the entry's ANSWER chunk as context
(never the question text), and results are de-duplicated per chunk.

Hybrid ranking: the final relevance score blends the semantic similarity
with a keyword score from services/lexical_index.py, so topics that hinge
on a specific word (PAN, Jan Dhan, cheque, nominee) are not confused.
The confidence gate applies to this blended score.
Measured effect of both: see tests/eval_rag.py.
"""
import json
import re

from core.config import KNOWLEDGE_BASE_PATH
from services.embedding_service import embedding_service
from services.lexical_index import LexicalIndex
from services.vector_store import Chunk, InMemoryVectorStore, ScoredChunk

# --- Tunable retrieval parameters ---
CHUNK_SIZE_CHARS = 350  # target max characters per chunk
CHUNK_OVERLAP_SENTENCES = 1  # sentences repeated between consecutive chunks of the same doc, for context continuity
TOP_K = 3
MIN_CONFIDENCE = 0.42  # relevance below this -> "don't know", don't call the LLM at all
INDEX_EXAMPLE_QUESTIONS = True  # also match against each entry's example "questions" (see module docstring)
LEXICAL_WEIGHT = 0.3  # share of the relevance score from keyword matching; 0 = semantic only

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def _split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_SPLIT_RE.split(text.strip()) if s.strip()]


def _chunk_document(doc_id: str, topic: str, content: str) -> list[Chunk]:
    """Greedy sentence-boundary chunking: accumulate sentences into a chunk
    until adding the next one would exceed CHUNK_SIZE_CHARS, then start a
    new chunk that repeats the last CHUNK_OVERLAP_SENTENCES sentence(s) for
    continuity. The topic is prepended to every chunk's text so a chunk
    embedded and retrieved on its own still carries its subject line.

    The current knowledge base entries are short (2-4 sentences each), so
    most produce a single chunk today — this chunker is sized for when the
    knowledge base grows to longer documents, not for the current content.
    """
    sentences = _split_sentences(content)
    if not sentences:
        return [Chunk(doc_id=doc_id, topic=topic, text=f"{topic}: {content}", chunk_index=0)]

    chunks: list[Chunk] = []
    current: list[str] = []
    current_len = 0

    def _flush():
        if current:
            text = f"{topic}: " + " ".join(current)
            chunks.append(Chunk(doc_id=doc_id, topic=topic, text=text, chunk_index=len(chunks)))

    for sentence in sentences:
        if current and current_len + len(sentence) + 1 > CHUNK_SIZE_CHARS:
            _flush()
            current = current[-CHUNK_OVERLAP_SENTENCES:] if CHUNK_OVERLAP_SENTENCES else []
            current_len = sum(len(s) + 1 for s in current)
        current.append(sentence)
        current_len += len(sentence) + 1
    _flush()

    return chunks


def _load_knowledge_base() -> list[dict]:
    with open(KNOWLEDGE_BASE_PATH, encoding="utf-8") as f:
        return json.load(f)


def _doc_topic(doc: dict) -> str:
    # Supports both the original knowledge-base schema (topic/content)
    # and the synthetic demo dataset schema (category/title/content).
    return doc.get("topic") or doc.get("title") or doc.get("category") or "Banking guidance"


def _load_and_chunk_knowledge_base() -> list[Chunk]:
    chunks: list[Chunk] = []
    for doc in _load_knowledge_base():
        chunks.extend(_chunk_document(doc["id"], _doc_topic(doc), doc["content"]))
    return chunks


def _load_example_questions() -> list[tuple[str, str]]:
    """(doc_id, example question) pairs from each entry's "questions" list."""
    return [(doc["id"], q) for doc in _load_knowledge_base() for q in doc.get("questions") or []]


class SemanticRetriever:
    """Owns the vector index for the knowledge base. Built lazily on first
    use (not at import time) so importing this module never triggers an
    embedding-model load or network access — useful for tests and for fast
    app startup when retrieval isn't needed yet."""

    def __init__(self, index_example_questions: bool | None = None, lexical_weight: float | None = None):
        self._store: InMemoryVectorStore | None = None
        self._lexical: LexicalIndex | None = None
        self._index_questions = index_example_questions
        self._lexical_weight = lexical_weight

    def _ensure_index(self) -> InMemoryVectorStore:
        if self._store is None:
            chunks = _load_and_chunk_knowledge_base()
            store = InMemoryVectorStore()
            store.add(chunks, embedding_service.embed([c.text for c in chunks]))

            use_questions = INDEX_EXAMPLE_QUESTIONS if self._index_questions is None else self._index_questions
            if use_questions:
                # Each example question is stored as another vector for its
                # entry's first answer chunk, so a match returns the answer.
                first_chunk = {c.doc_id: c for c in reversed(chunks)}
                pairs = [(first_chunk[doc_id], q) for doc_id, q in _load_example_questions() if doc_id in first_chunk]
                if pairs:
                    store.add([c for c, _ in pairs], embedding_service.embed([q for _, q in pairs]))
            docs = _load_knowledge_base()
            self._lexical = LexicalIndex(
                [d["id"] for d in docs],
                [" ".join([_doc_topic(d), " ".join(d.get("keywords") or []), d["content"], " ".join(d.get("questions") or [])]) for d in docs],
            )
            self._store = store
        return self._store

    def retrieve(self, query: str, top_k: int = TOP_K) -> list[ScoredChunk]:
        store = self._ensure_index()
        query_vector = embedding_service.embed([query])[0]
        # Best semantic score per chunk (an entry can match through its
        # answer text and several example questions).
        best: dict[tuple[str, int], ScoredChunk] = {}
        for r in store.search(query_vector, len(store)):
            key = (r.chunk.doc_id, r.chunk.chunk_index)
            if key not in best:
                best[key] = r
        weight = LEXICAL_WEIGHT if self._lexical_weight is None else self._lexical_weight
        lexical = self._lexical.scores(query) if weight else {}
        blended = [
            ScoredChunk(chunk=r.chunk, score=(1 - weight) * r.score + weight * lexical.get(r.chunk.doc_id, 0.0))
            for r in best.values()
        ]
        blended.sort(key=lambda r: r.score, reverse=True)
        return blended[:top_k]


retriever = SemanticRetriever()


def is_confident(results: list[ScoredChunk], threshold: float = MIN_CONFIDENCE) -> bool:
    return bool(results) and results[0].score >= threshold


def build_context(results: list[ScoredChunk]) -> str:
    """Formats retrieved chunks for the LLM prompt, WITH source metadata
    (topic, document id, chunk index, similarity score) so the model — and
    a human reviewing the conversation log — can see exactly which policy
    passage backed the answer. Only the top-K chunks are included here,
    never the full knowledge base."""
    return "\n\n".join(
        f"[Source: {r.chunk.topic} | doc={r.chunk.doc_id} chunk={r.chunk.chunk_index} relevance={r.score:.2f}]\n{r.chunk.text}"
        for r in results
    )


# Fallback shown when no retrieved chunk clears MIN_CONFIDENCE — i.e. we
# have no trustworthy grounding for an answer, so we say so instead of
# guessing. Translations are machine-assisted approximations; a native
# speaker should review these before a real deployment.
GROUNDING_FALLBACK = {
    "en": "I'm sorry, I couldn't confidently find this in our bank policies. Please ask a branch staff member for help with this.",
    "hi": "मुझे खेद है, मुझे हमारी नीतियों में इस बारे में पक्की जानकारी नहीं मिली। कृपया शाखा कर्मचारी से सहायता लें।",
    "mr": "क्षमस्व, मला आमच्या धोरणांमध्ये याबद्दल खात्रीशीर माहिती मिळाली नाही. कृपया शाखा कर्मचाऱ्यांची मदत घ्या.",
    "te": "క్షమించండి, మా విధానాలలో దీని గురించి నాకు నమ్మకమైన సమాచారం దొరకలేదు. దయచేసి బ్రాంచ్ సిబ్బంది సహాయం తీసుకోండి.",
    "kn": "ಕ್ಷಮಿಸಿ, ನಮ್ಮ ನೀತಿಗಳಲ್ಲಿ ಇದರ ಬಗ್ಗೆ ನನಗೆ ಖಚಿತವಾದ ಮಾಹಿತಿ ಸಿಗಲಿಲ್ಲ. ದಯವಿಟ್ಟು ಶಾಖೆಯ ಸಿಬ್ಬಂದಿಯ ಸಹಾಯ ಪಡೆಯಿರಿ.",
}


def grounding_fallback(language: str) -> str:
    return GROUNDING_FALLBACK.get(language, GROUNDING_FALLBACK["en"])
