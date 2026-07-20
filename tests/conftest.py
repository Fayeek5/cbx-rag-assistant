"""Shared pytest fixtures.

Retrieval tests use the REAL bge-small embedding model (already cached on this
machine) so they exercise the true pipeline. LLM calls are always MOCKED so the
suite is deterministic, fast, and needs no Ollama/network.
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings  # noqa: E402


@pytest.fixture
def isolated_store(tmp_path, monkeypatch):
    """Point the vector store at a throwaway Chroma dir + collection."""
    monkeypatch.setattr(settings, "chroma_dir", str(tmp_path / "chroma"))
    monkeypatch.setattr(settings, "collection_name", "test_collection")
    from app import vectorstore
    vectorstore.reset()
    return vectorstore


@pytest.fixture
def populated_store(isolated_store):
    """A store pre-loaded with a few known chunks."""
    from app.ingest import Chunk
    isolated_store.add_chunks([
        Chunk(text="A 401 Unauthorized means the Bearer token expired after 30 minutes.",
              source="auth.md", chunk_index=0),
        Chunk(text="Codelist fields must be sent as {code, name, version} objects, not plain strings.",
              source="api.md", chunk_index=0),
        Chunk(text="Code Lists must be configured before creating an item; they power all dropdowns.",
              source="onboarding.md", chunk_index=0),
    ])
    return isolated_store


@pytest.fixture
def mock_llm(monkeypatch):
    """Replace the LLM with a deterministic echo so rag/api tests don't need Ollama.

    The fake returns a canned answer that includes a Sources line (to test
    stripping) and, when the prompt clearly lacks the answer keyword, the refusal.
    Tests can override `holder['reply']`.
    """
    holder = {"reply": "This is a grounded answer.\nSources: api.md"}

    def fake_chat_messages(messages, model=None):
        return holder["reply"]

    def fake_chat(system, user, model=None):
        return holder["reply"]

    monkeypatch.setattr("app.llm.chat_messages", fake_chat_messages)
    monkeypatch.setattr("app.llm.chat", fake_chat)
    # rag imports these names directly, patch there too
    monkeypatch.setattr("app.rag.chat_messages", fake_chat_messages)
    monkeypatch.setattr("app.rag.chat", fake_chat)
    return holder
