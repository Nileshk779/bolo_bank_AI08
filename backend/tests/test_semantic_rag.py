"""
Tests for semantic retrieval (services/rag_service.py, vector_store.py).

Honesty note on methodology: the real embedding model
(paraphrase-multilingual-MiniLM-L12-v2) requires downloading ~118MB from
huggingface.co, which is not reachable from this sandboxed test
environment (confirmed: `google.auth`-style network egress is allowlisted
per-domain, and huggingface.co is not on it). These tests therefore mock
`embedding_service.embed()` and construct vectors *by intent* — e.g. "this
paraphrased query should end up close in vector space to this chunk" —
rather than deriving them from any real or proxy encoder.

This validates what our own code is responsible for and can go wrong in:
cosine ranking, top-K selection, the confidence threshold, source metadata
in the built context, and the LLM being skipped entirely on a low-confidence
match. It does NOT validate the real model's semantic quality (whether it
actually places a Hindi paraphrase close to its English equivalent) — that
requires running with real network access to download the model, e.g. in
CI or a normal deployment, and should be done before relying on this in
production.
"""
from unittest.mock import patch

import numpy as np
import pytest

from services import rag_service
from services.embedding_service import embedding_service
from services.rag_service import (
    MIN_CONFIDENCE,
    _load_and_chunk_knowledge_base,
    build_context,
    is_confident,
    retriever,
)

DIM = 32


def _unit(v: np.ndarray) -> np.ndarray:
    return (v / np.linalg.norm(v)).astype("float32")


def _base_vector(seed: int) -> np.ndarray:
    return _unit(np.random.default_rng(seed).normal(size=DIM))


def _blend(v1: np.ndarray, v2: np.ndarray, weight: float) -> np.ndarray:
    """weight=1.0 -> identical to v1 (cos sim 1.0); weight=0.0 -> pure v2."""
    return _unit(weight * v1 + (1 - weight) * v2)


@pytest.fixture(autouse=True)
def reset_index():
    """Each test builds its own index under its own mocked embedder, so
    tests never see another test's cached index."""
    retriever._store = None
    yield
    retriever._store = None


@pytest.fixture
def real_chunks():
    return _load_and_chunk_knowledge_base()


def _chunk_by_topic(chunks, topic_substr: str):
    return next(c for c in chunks if topic_substr.lower() in c.topic.lower())


def _install_fake_embedder(chunk_vectors: dict[str, np.ndarray], query_vector_by_text: dict[str, np.ndarray]):
    """chunk_vectors: {chunk.text: vector} used when embedding KB chunks
    while building the index. query_vector_by_text: {query_string: vector}
    used when embedding a search query. Anything not explicitly listed
    falls back to a random-but-deterministic unrelated vector, so it never
    accidentally ranks near the top of a test's results."""

    def _fake_embed(texts: list[str]) -> np.ndarray:
        out = []
        for t in texts:
            if t in chunk_vectors:
                out.append(chunk_vectors[t])
            elif t in query_vector_by_text:
                out.append(query_vector_by_text[t])
            else:
                out.append(_base_vector(abs(hash(t)) % (2**31)))
        return np.vstack(out).astype("float32")

    return patch.object(embedding_service, "embed", side_effect=_fake_embed)


# --- Chunking (pure logic, no embedding model needed) ---


def test_short_kb_documents_produce_one_chunk_each(real_chunks):
    # The current knowledge base entries are short (2-4 sentences); confirms
    # the chunker doesn't over-split them.
    by_doc = {}
    for c in real_chunks:
        by_doc.setdefault(c.doc_id, []).append(c)
    assert all(len(v) == 1 for v in by_doc.values())
    assert len(by_doc) == 6


def test_long_document_is_split_into_multiple_overlapping_chunks():
    long_content = " ".join(f"This is filler sentence number {i} about a policy detail." for i in range(20))
    chunks = rag_service._chunk_document("synthetic001", "Synthetic long policy", long_content)
    assert len(chunks) > 1
    # Overlap: the last sentence of one chunk should also appear at the
    # start of the next, for context continuity across the split.
    first_chunk_sentences = rag_service._split_sentences(chunks[0].text.split(": ", 1)[1])
    second_chunk_sentences = rag_service._split_sentences(chunks[1].text.split(": ", 1)[1])
    assert first_chunk_sentences[-1] == second_chunk_sentences[0]


def test_chunks_carry_source_metadata(real_chunks):
    for c in real_chunks:
        assert c.doc_id and c.topic and c.text
        assert isinstance(c.chunk_index, int)


# --- Vector store math (no embedding model needed) ---


def test_vector_store_ranks_by_cosine_similarity():
    from services.vector_store import Chunk, InMemoryVectorStore

    store = InMemoryVectorStore()
    a = _base_vector(1)
    b = _base_vector(2)
    c = _base_vector(3)
    chunks = [Chunk("d1", "A", "chunk a", 0), Chunk("d2", "B", "chunk b", 0), Chunk("d3", "C", "chunk c", 0)]
    store.add(chunks, np.vstack([a, b, c]))

    # Query identical to `a` should rank `a` first with score ~1.0
    results = store.search(a, top_k=3)
    assert results[0].chunk.doc_id == "d1"
    assert results[0].score == pytest.approx(1.0, abs=1e-5)
    assert results[0].score >= results[1].score >= results[2].score


def test_vector_store_empty_returns_nothing():
    from services.vector_store import InMemoryVectorStore

    store = InMemoryVectorStore()
    assert store.search(_base_vector(1), top_k=3) == []


# --- The 6 required retrieval scenarios ---


def test_1_exact_question_retrieves_correct_document(real_chunks):
    target = _chunk_by_topic(real_chunks, "savings account")
    target_vec = _base_vector(100)
    chunk_vectors = {c.text: (target_vec if c.doc_id == target.doc_id else _base_vector(200 + i)) for i, c in enumerate(real_chunks)}
    query = "To open a savings account, a customer needs: Aadhaar card, PAN card..."
    query_vec = target_vec  # exact/near-duplicate text -> essentially identical embedding

    with _install_fake_embedder(chunk_vectors, {query: query_vec}):
        results = retriever.retrieve(query)

    assert results[0].chunk.doc_id == target.doc_id
    assert is_confident(results)


def test_2_paraphrased_question_retrieves_same_document(real_chunks):
    """Different wording, same intent — e.g. 'What documents do I need to
    start a new account?' instead of 'How do I open a savings account?'.
    A real semantic model should place these close but not identical; we
    simulate that with a moderate blend rather than an exact match, and
    assert our threshold still recognizes it as confident."""
    target = _chunk_by_topic(real_chunks, "savings account")
    target_vec = _base_vector(101)
    unrelated = _base_vector(999)
    chunk_vectors = {c.text: (target_vec if c.doc_id == target.doc_id else _base_vector(300 + i)) for i, c in enumerate(real_chunks)}
    query = "What documents do I need to start a brand new bank account?"
    # Blended, not identical — simulates "related but reworded" rather than exact match.
    query_vec = _blend(target_vec, unrelated, weight=0.75)

    with _install_fake_embedder(chunk_vectors, {query: query_vec}):
        results = retriever.retrieve(query)

    assert results[0].chunk.doc_id == target.doc_id
    assert is_confident(results)


def test_3_different_language_question_retrieves_same_document(real_chunks):
    """Simulates a real multilingual embedding model placing a Hindi
    question in the same semantic neighborhood as its English KB match —
    something only the real model can actually verify, but our ranking/
    threshold code must handle correctly once that alignment exists."""
    target = _chunk_by_topic(real_chunks, "pension")
    target_vec = _base_vector(102)
    chunk_vectors = {c.text: (target_vec if c.doc_id == target.doc_id else _base_vector(400 + i)) for i, c in enumerate(real_chunks)}
    query = "वरिष्ठ नागरिकों के लिए बैंक में क्या सुविधाएं हैं?"  # "What facilities does the bank offer senior citizens?"
    query_vec = _blend(target_vec, _base_vector(998), weight=0.8)

    with _install_fake_embedder(chunk_vectors, {query: query_vec}):
        results = retriever.retrieve(query)

    assert results[0].chunk.doc_id == target.doc_id
    assert is_confident(results)


def test_4_irrelevant_question_is_not_confidently_matched_and_skips_the_llm(real_chunks):
    chunk_vectors = {c.text: _base_vector(500 + i) for i, c in enumerate(real_chunks)}
    query = "What's the weather like in Mumbai today?"
    query_vec = _base_vector(9001)  # unrelated to every KB vector by construction

    with _install_fake_embedder(chunk_vectors, {query: query_vec}):
        results = retriever.retrieve(query)
        assert not is_confident(results)

        with patch("services.ai_orchestrator.chat_completion") as mock_llm:
            reply = rag_service_generate_customer_reply_via_orchestrator(query, "en")
            mock_llm.assert_not_called()

    assert "branch staff" in reply["reply_local"].lower() or "staff member" in reply["reply_local"].lower()


def test_5_no_relevant_kb_content_returns_grounded_fallback_not_hallucination(real_chunks):
    chunk_vectors = {c.text: _base_vector(600 + i) for i, c in enumerate(real_chunks)}
    query = "Can I apply for a business credit card with airline miles rewards?"
    query_vec = _base_vector(9002)

    with _install_fake_embedder(chunk_vectors, {query: query_vec}):
        with patch("services.ai_orchestrator.chat_completion") as mock_llm:
            reply = rag_service_generate_customer_reply_via_orchestrator(query, "hi")
            mock_llm.assert_not_called()

    from services.rag_service import GROUNDING_FALLBACK

    assert reply["reply_local"] == GROUNDING_FALLBACK["hi"]
    assert reply["reply_english"] == GROUNDING_FALLBACK["en"]


def test_6_multiple_relevant_documents_returned_in_ranked_order(real_chunks):
    loan_chunk = _chunk_by_topic(real_chunks, "loan")
    balance_chunk = _chunk_by_topic(real_chunks, "minimum balance")
    account_chunk = _chunk_by_topic(real_chunks, "savings account")

    query_vec = _base_vector(700)
    chunk_vectors = {}
    for i, c in enumerate(real_chunks):
        if c.doc_id == loan_chunk.doc_id:
            chunk_vectors[c.text] = _blend(query_vec, _base_vector(1), weight=0.95)  # closest
        elif c.doc_id == balance_chunk.doc_id:
            chunk_vectors[c.text] = _blend(query_vec, _base_vector(2), weight=0.6)  # second closest
        elif c.doc_id == account_chunk.doc_id:
            chunk_vectors[c.text] = _blend(query_vec, _base_vector(3), weight=0.45)  # third closest
        else:
            chunk_vectors[c.text] = _base_vector(800 + i)  # unrelated

    query = "I want a loan but I'm not sure if my account balance qualifies"

    with _install_fake_embedder(chunk_vectors, {query: query_vec}):
        results = retriever.retrieve(query, top_k=3)

    assert [r.chunk.doc_id for r in results] == [loan_chunk.doc_id, balance_chunk.doc_id, account_chunk.doc_id]
    assert results[0].score >= results[1].score >= results[2].score

    context = build_context(results)
    # Source metadata (topic, doc id, chunk index, relevance score) must be present.
    for r in results:
        assert r.chunk.topic in context
        assert f"doc={r.chunk.doc_id}" in context


def rag_service_generate_customer_reply_via_orchestrator(query: str, language: str) -> dict:
    from services.ai_orchestrator import generate_customer_reply

    return generate_customer_reply(query, language, "simple")
