"""Hybrid retrieval + reranking + threshold."""
from __future__ import annotations

from app import retriever
from app.ingest import Chunk


def test_retrieve_ranks_relevant_first(populated_store):
    results = retriever.retrieve("how do I fix a 401 unauthorized error", top_k=3)
    assert results
    assert "401" in results[0]["text"]
    assert 0.0 <= results[0]["score"] <= 1.0


def test_bm25_arm_catches_exact_identifier(populated_store, monkeypatch):
    # add a chunk with a rare exact token an embedding might miss
    populated_store.add_chunks([
        Chunk(text="The field thinknessUOM is a known typo in the schema.",
              source="api.md", chunk_index=9),
    ])
    # clear the BM25 cache so it re-indexes with the new chunk
    retriever._bm25_index.cache_clear()
    results = retriever.retrieve("thinknessUOM", top_k=3)
    assert any("thinknessUOM" in r["text"] for r in results)


def test_relevant_query_passes_threshold(populated_store):
    results = retriever.retrieve("how do I fix a 401 unauthorized error", top_k=3)
    assert results and retriever.passes_threshold(results)


def test_threshold_gates_on_vector_score():
    # gate uses vscore (calibrated), not the reranker's tiny sigmoid
    assert retriever.passes_threshold([{"vscore": 0.9, "text": "x"}]) is True
    assert retriever.passes_threshold([{"vscore": 0.10, "text": "x"}]) is False


def test_passes_threshold_empty():
    assert retriever.passes_threshold([]) is False
