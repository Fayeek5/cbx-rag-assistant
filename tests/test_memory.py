"""Conversation memory: append, retrieve, cap, reset, session isolation."""
from __future__ import annotations

from app import memory


def test_empty_history_for_unknown_session():
    assert memory.get_history("nope-" + "x") == []


def test_append_and_get(monkeypatch):
    sid = "s-append"
    memory.reset(sid)
    memory.append(sid, "user", "hi")
    memory.append(sid, "assistant", "hello")
    hist = memory.get_history(sid)
    assert [m["role"] for m in hist] == ["user", "assistant"]
    assert hist[0]["content"] == "hi"


def test_history_is_capped(monkeypatch):
    from config import settings
    monkeypatch.setattr(settings, "history_turns", 2)  # cap = 2 turns = 4 messages
    sid = "s-cap"
    memory.reset(sid)
    for i in range(10):
        memory.append(sid, "user", f"q{i}")
        memory.append(sid, "assistant", f"a{i}")
    hist = memory.get_history(sid)
    assert len(hist) == 4  # only the most recent 2 turns
    assert hist[-1]["content"] == "a9"


def test_sessions_are_isolated():
    memory.reset("s-a"); memory.reset("s-b")
    memory.append("s-a", "user", "in A")
    memory.append("s-b", "user", "in B")
    assert memory.get_history("s-a")[0]["content"] == "in A"
    assert memory.get_history("s-b")[0]["content"] == "in B"


def test_reset_clears_session():
    sid = "s-reset"
    memory.append(sid, "user", "x")
    memory.reset(sid)
    assert memory.get_history(sid) == []


def test_empty_session_id_ignored():
    memory.append("", "user", "x")  # must not raise
    assert memory.get_history("") == []
