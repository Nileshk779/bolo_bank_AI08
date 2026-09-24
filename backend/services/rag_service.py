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
"""
import json
import re

from core.config import KNOWLEDGE_BASE_PATH
from services.embedding_service import embedding_service
from services.vector_store import Chunk, InMemoryVectorStore, ScoredChunk

# --- Tunable retrieval parameters ---
CHUNK_SIZE_CHARS = 350  # target max characters per chunk
CHUNK_OVERLAP_SENTENCES = 1  # sentences repeated between consecutive chunks of the same doc, for context continuity
TOP_K = 3
MIN_CONFIDENCE = 0.38  # cosine similarity below this -> "don't know", don't call the LLM at all

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


def _load_and_chunk_knowledge_base() -> list[Chunk]:
    with open(KNOWLEDGE_BASE_PATH, encoding="utf-8") as f:
        docs = json.load(f)

    chunks: list[Chunk] = []
    for doc in docs:
        # Supports both the original knowledge-base schema (topic/content)
        # and the synthetic demo dataset schema (category/title/content).
        topic = doc.get("topic") or doc.get("title") or doc.get("category") or "Banking guidance"
        chunks.extend(_chunk_document(doc["id"], topic, doc["content"]))
    return chunks


class SemanticRetriever:
    """Owns the vector index for the knowledge base. Built lazily on first
    use (not at import time) so importing this module never triggers an
    embedding-model load or network access — useful for tests and for fast
    app startup when retrieval isn't needed yet."""

    def __init__(self):
        self._store: InMemoryVectorStore | None = None

    def _ensure_index(self) -> InMemoryVectorStore:
        if self._store is None:
            chunks = _load_and_chunk_knowledge_base()
            vectors = embedding_service.embed([c.text for c in chunks])
            store = InMemoryVectorStore()
            store.add(chunks, vectors)
            self._store = store
        return self._store

    def retrieve(self, query: str, top_k: int = TOP_K) -> list[ScoredChunk]:
        store = self._ensure_index()
        query_vector = embedding_service.embed([query])[0]
        return store.search(query_vector, top_k)


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
