"""Vector store add/query/count/reset (isolated temp collection + real embeddings)."""
from __future__ import annotations

from app.ingest import Chunk


def test_add_and_count(isolated_store):
    assert isolated_store.count() == 0
    n = isolated_store.add_chunks([
        Chunk(text="hello world", source="a.md", chunk_index=0),
        Chunk(text="goodbye world", source="a.md", chunk_index=1),
    ])
    assert n == 2
    assert isolated_store.count() == 2


def test_add_empty_is_noop(isolated_store):
    assert isolated_store.add_chunks([]) == 0
    assert isolated_store.count() == 0


def test_query_returns_relevant_first(populated_store):
    results = populated_store.query("why do I get a 401 error", top_k=3)
    assert results
    assert "401" in results[0]["text"]
    # score/distance fields present and sane
    assert 0.0 <= results[0]["score"] <= 1.0
    assert results[0]["source"] == "auth.md"


def test_query_top_k_limits_results(populated_store):
    assert len(populated_store.query("anything", top_k=1)) == 1
    assert len(populated_store.query("anything", top_k=2)) == 2


def test_reset_clears(populated_store):
    assert populated_store.count() == 3
    populated_store.reset()
    assert populated_store.count() == 0


def test_upsert_is_idempotent(isolated_store):
    c = [Chunk(text="dup", source="a.md", chunk_index=0)]
    isolated_store.add_chunks(c)
    isolated_store.add_chunks(c)  # same id -> upsert, not duplicate
    assert isolated_store.count() == 1
