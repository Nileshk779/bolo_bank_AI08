"""
Embedding model wrapper.

Model: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
  - A compact (~118MB, 12-layer) multilingual sentence embedding model,
    fine-tuned for paraphrase/semantic-similarity, built on XLM-RoBERTa.
  - Chosen for the hackathon-MVP requirement to avoid heavy infrastructure:
    it runs comfortably on CPU with no GPU or external embedding API needed
    (Groq, our LLM provider, doesn't offer an embeddings endpoint), and
    downloads once (~118MB) from the Hugging Face Hub on first run.
  - Covers Hindi and English with official paraphrase-quality benchmarks.
    Marathi, Telugu, and Kannada are inside XLM-RoBERTa's 100-language
    pretraining set (so the model has *some* representation for them) but
    are not among the languages the paraphrase fine-tuning data explicitly
    targeted — see the "known limitations" note in the project report.
    Swapping to a model with stronger Indian-language coverage later (e.g.
    an Indic-specific sentence encoder) only requires changing MODEL_NAME
    below; nothing else in the retrieval pipeline depends on which model
    produces the vectors, only that embed() returns unit-normalized arrays.

Embeddings are L2-normalized, so cosine similarity between two vectors is
just their dot product — that's what InMemoryVectorStore relies on.
"""
import logging

import numpy as np

from core.exceptions import UpstreamServiceError

logger = logging.getLogger("bolobank.embeddings")

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


class EmbeddingService:
    def __init__(self):
        self._model = None

    def _load_model(self):
        if self._model is not None:
            return self._model
        try:
            from sentence_transformers import SentenceTransformer

            logger.info("Loading embedding model %s (first run downloads it, ~118MB)...", MODEL_NAME)
            self._model = SentenceTransformer(MODEL_NAME)
            logger.info("Embedding model loaded.")
        except Exception as exc:
            logger.error("Failed to load embedding model: %s", exc)
            raise UpstreamServiceError("Embedding model", str(exc)) from exc
        return self._model

    def embed(self, texts: list[str]) -> np.ndarray:
        """Returns an (n_texts, embedding_dim) float32 array of L2-normalized
        vectors — one per input string, same order as `texts`."""
        if not texts:
            return np.zeros((0, 384), dtype="float32")
        model = self._load_model()
        vectors = model.encode(texts, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False)
        return vectors.astype("float32")


# Single shared instance — the model is loaded once (lazily, on first use)
# and reused for every query and for building the knowledge-base index.
embedding_service = EmbeddingService()
