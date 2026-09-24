"""
Minimal vector store abstraction.

BaseVectorStore defines the only two operations retrieval actually needs:
add() and search(). InMemoryVectorStore is a numpy-backed implementation —
appropriate for a hackathon MVP with a knowledge base of a few dozen chunks,
where a dedicated vector database would be unnecessary infrastructure.

To migrate to pgvector, Qdrant, Pinecone, etc. later: implement a new class
with the same add()/search() signature (e.g. QdrantVectorStore) and swap the
one line in rag_service.py that constructs the store. Nothing else in the
codebase — chunking, embedding, retrieval, grounding — needs to change,
since none of it talks to the store's internals directly.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Chunk:
    """A retrievable unit of text plus the source metadata needed to cite it
    and to let the LLM (and, eventually, a human reviewer) trace an answer
    back to the exact policy document it came from."""

    doc_id: str
    topic: str
    text: str
    chunk_index: int  # position of this chunk within its source document


@dataclass(frozen=True)
class ScoredChunk:
    chunk: Chunk
    score: float  # cosine similarity, range [-1, 1] (practically [0, 1] for these embeddings)


class BaseVectorStore(ABC):
    @abstractmethod
    def add(self, chunks: list[Chunk], vectors: np.ndarray) -> None: ...

    @abstractmethod
    def search(self, query_vector: np.ndarray, top_k: int) -> list[ScoredChunk]: ...


class InMemoryVectorStore(BaseVectorStore):
    """Stores L2-normalized embedding vectors in a single numpy matrix, so
    cosine similarity for a query reduces to one matrix-vector dot product —
    O(n) per query, which is more than fast enough at this scale (rebuilt
    once at process startup from a knowledge base of a few dozen chunks)."""

    def __init__(self):
        self._chunks: list[Chunk] = []
        self._matrix: np.ndarray | None = None  # shape (n_chunks, embedding_dim)

    def add(self, chunks: list[Chunk], vectors: np.ndarray) -> None:
        if len(chunks) != vectors.shape[0]:
            raise ValueError("chunks and vectors must have the same length")
        self._chunks.extend(chunks)
        self._matrix = vectors if self._matrix is None else np.vstack([self._matrix, vectors])

    def search(self, query_vector: np.ndarray, top_k: int) -> list[ScoredChunk]:
        if self._matrix is None or len(self._chunks) == 0:
            return []
        scores = self._matrix @ query_vector  # cosine similarity, since both sides are unit-normalized
        top_k = min(top_k, len(self._chunks))
        top_indices = np.argpartition(-scores, top_k - 1)[:top_k]
        top_indices = top_indices[np.argsort(-scores[top_indices])]  # exact order within the top-k slice
        return [ScoredChunk(chunk=self._chunks[i], score=float(scores[i])) for i in top_indices]

    def __len__(self) -> int:
        return len(self._chunks)
