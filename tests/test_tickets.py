"""Ticket ingestion + agent-assist."""
from __future__ import annotations

import json

from app import tickets, rag


def test_ticket_to_chunk_shape():
    c = tickets.ticket_to_chunk({
        "id": "CBX-1", "summary": "500 on import", "description": "fails",
        "resolution": "send codelist as object", "component": "API"})
    assert c.source == "ticket:CBX-1"
    assert "Resolution: send codelist as object" in c.text
    assert "Problem: fails" in c.text


def test_load_tickets_jsonl(tmp_path):
    p = tmp_path / "t.jsonl"
    p.write_text(json.dumps({"id": "A", "summary": "s"}) + "\n" +
                 json.dumps({"id": "B", "summary": "s2"}) + "\n", encoding="utf-8")
    loaded = tickets.load_tickets(str(p))
    assert len(loaded) == 2 and loaded[0]["id"] == "A"


def test_tickets_to_chunks_skips_empty():
    chunks = tickets.tickets_to_chunks([{"id": "A", "summary": "x"}, {"foo": "bar"}])
    assert len(chunks) == 1


def test_assist_drafts_from_context(populated_store, mock_llm):
    # add a resolved ticket resembling a known issue
    populated_store.add_chunks(tickets.tickets_to_chunks([{
        "id": "CBX-9", "summary": "500 on color import",
        "resolution": "codelist must be {code, name, version}"}]))
    mock_llm["reply"] = "1. Probable cause: codelist sent as string [1]. 2. Send object shape. 3. Confidence: High"
    out = rag.assist("color import returns 500 error")
    assert out["draft"] and out["passages"]
    assert "confident" in out
