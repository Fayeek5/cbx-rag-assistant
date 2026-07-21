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


def test_ask_stream_emits_tokens_and_meta(client, mock_llm, monkeypatch):
    # stream client uses chat_messages_stream; make it yield deltas
    def fake_stream(messages, model=None):
        yield "Codelist fields are "
        yield "{code, name, version}."
    monkeypatch.setattr("app.rag.chat_messages_stream", fake_stream)
    monkeypatch.setattr("app.rag._suggest_followups", lambda q, a: ["What is ELC?"])

    with client.stream("POST", "/ask/stream",
                       json={"question": "codelist shape?", "session_id": "s"}) as r:
        assert r.status_code == 200
        body = "".join(r.iter_text())
    assert "token" in body and "meta" in body
    assert "Codelist fields are" in body


def test_feedback_endpoint(client, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # feedback.jsonl written under cwd/data
    r = client.post("/feedback", json={
        "question": "q?", "answer": "a.", "rating": "up", "session_id": "s"})
    assert r.status_code == 200
    assert (tmp_path / "data" / "feedback.jsonl").exists()


def test_ask_requires_question(client):
    r = client.post("/ask", json={})
    assert r.status_code == 422  # pydantic validation error


def test_list_connectors(client):
    r = client.get("/connectors")
    assert r.status_code == 200
    names = {c["name"] for c in r.json()["connectors"]}
    assert names == {"jira", "zendesk", "freshservice", "generic"}
    # with no creds set, all report not configured
    assert all(c["configured"] is False for c in r.json()["connectors"])


def test_sync_unconfigured_returns_400(client):
    r = client.post("/connectors/jira/sync", json={"dry_run": True})
    assert r.status_code == 400


def test_sync_unknown_connector_404(client):
    r = client.post("/connectors/nope/sync", json={})
    assert r.status_code == 404
