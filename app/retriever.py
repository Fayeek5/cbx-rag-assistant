"""Hybrid retrieval + cross-encoder reranking.

Pipeline for a query:
  1. VECTOR arm  — top candidate_k by embedding similarity (Chroma).
  2. BM25 arm    — top candidate_k by keyword overlap over ALL chunks.
  3. MERGE       — union of both candidate sets (dedup by id).
  4. RERANK      — a cross-encoder scores (query, chunk) pairs directly; this is
                   far more accurate than cosine for ordering the final few.
  5. THRESHOLD   — if the best reranked score (0-1) is below min_relevance, the
                   caller treats it as "not in the docs" (a HARD grounding gate).

Each arm/step is individually toggle-able via config, so you can measure the
contribution of each. Falls back gracefully to pure vector search if optional
pieces are disabled or unavailable.
"""
from __future__ import annotations

import math
import re
from functools import lru_cache

from config import settings
from app import vectorstore


# ── BM25 keyword arm ─────────────────────────────────────────────────────
def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9_]+", text.lower())


@lru_cache(maxsize=4)
def _bm25_index(collection_signature: str):
    """Build (and cache) a BM25 index over every chunk in the collection.
    Cache key includes the chunk count so it rebuilds after re-ingestion."""
    from rank_bm25 import BM25Okapi

    ids, docs, metas = vectorstore.all_chunks()
    corpus_tokens = [_tokenize(d) for d in docs]
    bm25 = BM25Okapi(corpus_tokens) if corpus_tokens else None
    return bm25, ids, docs, metas


def _bm25_candidates(query: str, k: int) -> list[dict]:
    sig = f"{settings.collection_name}:{vectorstore.count()}"
    bm25, ids, docs, metas = _bm25_index(sig)
    if not bm25:
        return []
    scores = bm25.get_scores(_tokenize(query))
    ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
    return [{"id": ids[i], "text": docs[i], "source": metas[i].get("source"),
             "chunk_index": metas[i].get("chunk_index")} for i in ranked if scores[i] > 0]


# ── Cross-encoder reranker ───────────────────────────────────────────────
@lru_cache(maxsize=1)
def _reranker():
    from sentence_transformers import CrossEncoder
    return CrossEncoder(settings.reranker_model)


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


# ── Public API ───────────────────────────────────────────────────────────
def retrieve(query: str, top_k: int | None = None) -> list[dict]:
    """Return the best passages for a query using hybrid + rerank + threshold.
    Each result has text/source/chunk_index plus a normalized 'score' (0-1)."""
    k = top_k or settings.top_k
    cand_k = max(settings.candidate_k, k)

    # 1. vector arm (also our fallback if everything else is off)
    vector_hits = vectorstore.query(query, top_k=cand_k)

    if not settings.use_hybrid and not settings.use_reranker:
        return vector_hits[:k]

    # 2+3. merge vector + BM25 candidates, dedup by id
    merged: dict[str, dict] = {}
    for h in vector_hits:
        merged[f"{h['source']}::{h['chunk_index']}"] = {
            "text": h["text"], "source": h["source"], "chunk_index": h["chunk_index"]}
    if settings.use_hybrid:
        for h in _bm25_candidates(query, cand_k):
            merged.setdefault(h["id"], {
                "text": h["text"], "source": h["source"], "chunk_index": h["chunk_index"]})

    candidates = list(merged.values())
    if not candidates:
        return []

    # 4. rerank
    if settings.use_reranker:
        pairs = [(query, c["text"]) for c in candidates]
        raw = _reranker().predict(pairs)
        for c, s in zip(candidates, raw):
            c["score"] = _sigmoid(float(s))
        candidates.sort(key=lambda c: c["score"], reverse=True)
    else:
        # keep vector order; carry its similarity score
        for c, h in zip(candidates, vector_hits):
            c["score"] = h.get("score", 0.0)

    return candidates[:k]


def passes_threshold(passages: list[dict]) -> bool:
    """True if the best passage is relevant enough to answer from (hard gate)."""
    if not passages:
        return False
    return passages[0].get("score", 0.0) >= settings.min_relevance
