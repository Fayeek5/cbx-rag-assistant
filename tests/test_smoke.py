"""Smoke tests that need NO LLM and NO network.

They verify the retrieval half of the pipeline (chunking + embeddings + vector
store), which is where most RAG quality problems actually live. Run:

    source .venv/bin/activate
    python -m pytest tests/ -v         # or: python tests/test_smoke.py
"""
from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_chunking_splits_text():
    from app.ingest import chunk_text

    text = "\n\n".join(f"Paragraph number {i} with some filler words." for i in range(50))
    chunks = chunk_text(text, source="mem")
    assert len(chunks) > 1
    assert all(c.text for c in chunks)
    assert chunks[0].chunk_index == 0


def test_retrieval_finds_relevant_chunk():
    """End-to-end retrieval on a throwaway collection."""
    from config import settings

    # isolate the test in a temp Chroma dir + unique collection
    tmp = tempfile.mkdtemp()
    settings.chroma_dir = tmp
    settings.collection_name = "smoke_test"

    from app import vectorstore
    from app.ingest import Chunk

    vectorstore.reset()
    vectorstore.add_chunks([
        Chunk(text="A 401 Unauthorized means the token expired.", source="a.md", chunk_index=0),
        Chunk(text="Widgets belong to a category which must exist first.", source="b.md", chunk_index=1),
        Chunk(text="Rate limit is 100 requests per minute per token.", source="c.md", chunk_index=2),
    ])

    results = vectorstore.query("why do I get a 401 error?", top_k=1)
    assert results, "expected at least one result"
    assert "401" in results[0]["text"], f"wrong chunk retrieved: {results[0]['text']}"
    print("Top hit:", results[0]["text"], "| score:", round(results[0]["score"], 3))


if __name__ == "__main__":
    test_chunking_splits_text()
    print("chunking OK")
    test_retrieval_finds_relevant_chunk()
    print("retrieval OK")
