"""Telemetry logging + metrics aggregation."""
from __future__ import annotations

import os

import pytest


@pytest.fixture
def temp_log(tmp_path, monkeypatch):
    import app.telemetry as t
    monkeypatch.setattr(t, "_LOG_PATH", str(tmp_path / "requests.jsonl"))
    monkeypatch.chdir(tmp_path)
    return t


def test_log_and_metrics(temp_log):
    t = temp_log
    t.log_turn(session_id="s", question="what is ELC?", intent="doc",
               answer="ELC is landed cost.", sources=["/x/kb.md"],
               top_score=0.8, latency_ms=1200, refused=False)
    t.log_turn(session_id="s", question="capital of France?", intent="doc",
               answer="I don't have that in the documentation.", sources=[],
               top_score=0.4, latency_ms=800, refused=True)
    t.log_turn(session_id="s", question="hi", intent="smalltalk",
               answer="Hello!", sources=[], top_score=None, latency_ms=100, refused=False)

    m = t.metrics()
    assert m["total_requests"] == 3
    assert m["doc_questions"] == 2
    assert m["refusals"] == 1
    assert m["refusal_rate"] == 0.5
    assert m["intents"]["doc"] == 2 and m["intents"]["smalltalk"] == 1
    assert m["latency_ms"]["avg"] is not None
    assert any(s["source"] == "kb.md" for s in m["top_sources"])
    assert m["recent"][0]["q"] == "hi"  # most recent first


def test_question_is_redacted_in_log(temp_log):
    t = temp_log
    t.log_turn(session_id="s", question="my email is a@b.com", intent="doc",
               answer="ok", sources=[], top_score=0.9, latency_ms=10, refused=False)
    import json
    with open(t._LOG_PATH, encoding="utf-8") as f:
        rec = json.loads(f.readline())
    assert "a@b.com" not in rec["question"]
    assert "[REDACTED_EMAIL]" in rec["question"]


def test_metrics_empty(temp_log):
    assert temp_log.metrics()["total_requests"] == 0
