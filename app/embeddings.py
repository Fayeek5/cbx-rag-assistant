"""Embedding model wrapper.

Loads bge-small-en-v1.5 once and reuses it. Runs on CPU by default, which is
plenty fast for this model. bge models expect a short instruction prefix on the
*query* side (not on stored passages) for best retrieval quality.
"""
from __future__ import annotations

from functools import lru_cache

from sentence_transformers import SentenceTransformer

from config import settings

# bge models recommend this prefix for queries only.
_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


@lru_cache(maxsize=1)
def _model() -> SentenceTransformer:
    return SentenceTransformer(settings.embedding_model)


def embed_passages(texts: list[str]) -> list[list[float]]:
    """Embed documents/chunks to store in the vector DB."""
    vecs = _model().encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return [v.tolist() for v in vecs]


def embed_query(text: str) -> list[float]:
    """Embed a user query (with the bge search prefix)."""
    vec = _model().encode(_QUERY_PREFIX + text, normalize_embeddings=True, show_progress_bar=False)
    return vec.tolist()
