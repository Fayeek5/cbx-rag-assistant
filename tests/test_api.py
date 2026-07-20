"""API endpoints via FastAPI TestClient (LLM mocked, real retrieval)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(populated_store, mock_llm):
    from app.api import app
    return TestClient(app)


def test_chat_ui_served(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "<title>CBX Assistant</title>" in r.text


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["indexed_chunks"] == 3


def test_search_endpoint(client):
    r = client.post("/search", json={"query": "401 error", "top_k": 2})
    assert r.status_code == 200
    results = r.json()["results"]
    assert len(results) == 2
    assert "401" in results[0]["text"]


def test_ask_endpoint(client, mock_llm):
    mock_llm["reply"] = "Codelist fields are {code, name, version}.\nSources: api.md"
    r = client.post("/ask", json={"question": "codelist shape?", "session_id": "api-1"})
    assert r.status_code == 200
    body = r.json()
    assert body["answer"] == "Codelist fields are {code, name, version}."
    assert body["session_id"] == "api-1"
    assert body["sources"]


def test_ask_refusal(client, mock_llm):
    mock_llm["reply"] = "I don't have that in the documentation."
    r = client.post("/ask", json={"question": "capital of France?", "session_id": "api-2"})
    body = r.json()
    assert body["answer"] == "I don't have that in the documentation."
    assert body["sources"] == []


def test_reset_endpoint(client):
    r = client.post("/reset", json={"session_id": "api-1"})
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_ask_requires_question(client):
    r = client.post("/ask", json={})
    assert r.status_code == 422  # pydantic validation error
