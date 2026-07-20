"""Vector store wrapper around Chroma (persistent, local, single-file DB).

We pass our own embeddings in explicitly (embedding_function=None) so the store
never tries to download its own model — the embedding model is owned by
app/embeddings.py. Each stored record keeps the chunk text + source metadata.
"""
from __future__ import annotations

import logging
import os

# Must be set BEFORE importing chromadb so its telemetry client reads it.
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

import chromadb
from chromadb.config import Settings as ChromaSettings

from config import settings

# Chroma's bundled telemetry has a posthog version bug that logs a harmless
# error on every call even when telemetry is disabled. Silence that logger.
logging.getLogger("chromadb.telemetry.product.posthog").setLevel(logging.CRITICAL)
from app.embeddings import embed_passages, embed_query
from app.ingest import Chunk


def _client() -> chromadb.ClientAPI:
    # anonymized_telemetry=False silences Chroma's telemetry warnings/logs.
    return chromadb.PersistentClient(
        path=settings.chroma_dir,
        settings=ChromaSettings(anonymized_telemetry=False),
    )


def _collection():
    return _client().get_or_create_collection(
        name=settings.collection_name,
        metadata={"hnsw:space": "cosine"},
    )


def add_chunks(chunks: list[Chunk]) -> int:
    """Embed and upsert chunks. Returns the number added."""
    if not chunks:
        return 0
    col = _collection()
    ids = [f"{c.source}::{c.chunk_index}" for c in chunks]
    docs = [c.text for c in chunks]
    metas = [{"source": c.source, "chunk_index": c.chunk_index} for c in chunks]
    embeddings = embed_passages(docs)
    col.upsert(ids=ids, documents=docs, metadatas=metas, embeddings=embeddings)
    return len(chunks)


def query(text: str, top_k: int | None = None) -> list[dict]:
    """Return the top-k most similar chunks for a query string."""
    k = top_k or settings.top_k
    col = _collection()
    res = col.query(
        query_embeddings=[embed_query(text)],
        n_results=k,
        include=["documents", "metadatas", "distances"],
    )
    out: list[dict] = []
    for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
        out.append({
            "text": doc,
            "source": meta.get("source"),
            "chunk_index": meta.get("chunk_index"),
            "distance": dist,          # cosine distance: lower = more similar
            "score": 1.0 - dist,       # convenience similarity score
        })
    return out


def all_chunks() -> tuple[list[str], list[str], list[dict]]:
    """Return (ids, documents, metadatas) for every stored chunk — used to build
    the BM25 keyword index."""
    res = _collection().get(include=["documents", "metadatas"])
    return res.get("ids", []), res.get("documents", []), res.get("metadatas", [])


def count() -> int:
    return _collection().count()


def reset() -> None:
    """Drop the collection (used before a clean re-ingest)."""
    try:
        _client().delete_collection(settings.collection_name)
    except Exception:
        pass
