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
# Ordering blends the calibrated vector similarity with the reranker so the
# reranker refines the order but can NEVER bury a strong vector hit. The relevance
# gate uses the vector similarity ('vscore', 0-1, well-calibrated) — NOT the
# reranker's sigmoid, which is tiny even for good matches.
_RERANK_WEIGHT = 0.4


def retrieve(query: str, top_k: int | None = None) -> list[dict]:
    """Return the best passages using hybrid candidates + reranked ordering.
    Each result carries 'vscore' (vector similarity, used for gating + display as
    'score') and 'rscore' (reranker confidence)."""
    k = top_k or settings.top_k
    cand_k = max(settings.candidate_k, k)

    # 1. vector arm — calibrated 0-1 similarity
    vector_hits = vectorstore.query(query, top_k=cand_k)

    merged: dict[str, dict] = {}
    for h in vector_hits:
        cid = f"{h['source']}::{h['chunk_index']}"
        merged[cid] = {"text": h["text"], "source": h["source"],
                       "chunk_index": h["chunk_index"], "vscore": h.get("score", 0.0)}
    # 2. BM25 arm — recall for exact identifiers (no vector score of its own)
    if settings.use_hybrid:
        for h in _bm25_candidates(query, cand_k):
            merged.setdefault(h["id"], {"text": h["text"], "source": h["source"],
                                        "chunk_index": h["chunk_index"], "vscore": 0.0})

    candidates = list(merged.values())
    if not candidates:
        return []

    # 3. rerank for ordering, blended with vector so strong vector hits stay up
    if settings.use_reranker:
        raw = _reranker().predict([(query, c["text"]) for c in candidates])
        for c, s in zip(candidates, raw):
            c["rscore"] = _sigmoid(float(s))
            c["final"] = (1 - _RERANK_WEIGHT) * c["vscore"] + _RERANK_WEIGHT * c["rscore"]
    else:
        for c in candidates:
            c["rscore"] = 0.0
            c["final"] = c["vscore"]

    candidates.sort(key=lambda c: c["final"], reverse=True)
    for c in candidates:
        c["score"] = c["vscore"]  # displayed/returned score = calibrated similarity
    return candidates[:k]


def passes_threshold(passages: list[dict]) -> bool:
    """Hard relevance gate: True only if some passage's VECTOR similarity clears
    min_relevance. Vector scores are calibrated (relevant ~0.6+, off-topic lower),
    unlike the reranker's near-zero sigmoids."""
    if not passages:
        return False
    return max(p.get("vscore", p.get("score", 0.0)) for p in passages) >= settings.min_relevance
