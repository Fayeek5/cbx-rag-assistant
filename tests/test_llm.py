"""LLM client: message payload shape and load-balancer -> backend failover."""
from __future__ import annotations

import httpx
import pytest

from app import llm


class _Resp:
    def __init__(self, content):
        self._c = content
    def raise_for_status(self):
        pass
    def json(self):
        return {"message": {"content": self._c}}


def test_chat_messages_returns_content(monkeypatch):
    called = {}
    def fake_post(url, json=None, timeout=None):
        called["url"] = url
        called["messages"] = json["messages"]
        return _Resp("hello from llm")
    monkeypatch.setattr(httpx, "post", fake_post)

    out = llm.chat_messages([{"role": "user", "content": "hi"}])
    assert out == "hello from llm"
    assert called["messages"] == [{"role": "user", "content": "hi"}]


def test_failover_to_second_target(monkeypatch):
    calls = []
    def fake_post(url, json=None, timeout=None):
        calls.append(url)
        if len(calls) == 1:
            raise httpx.ConnectError("LB down")  # first target (LB) fails
        return _Resp("recovered")
    monkeypatch.setattr(httpx, "post", fake_post)

    out = llm.chat_messages([{"role": "user", "content": "hi"}])
    assert out == "recovered"
    assert len(calls) >= 2  # tried LB, then a backend


def test_all_targets_fail_raises(monkeypatch):
    def fake_post(url, json=None, timeout=None):
        raise httpx.ConnectError("everything down")
    monkeypatch.setattr(httpx, "post", fake_post)

    with pytest.raises(RuntimeError):
        llm.chat_messages([{"role": "user", "content": "hi"}])


def test_chat_wrapper_builds_system_user(monkeypatch):
    captured = {}
    def fake_post(url, json=None, timeout=None):
        captured["messages"] = json["messages"]
        return _Resp("ok")
    monkeypatch.setattr(httpx, "post", fake_post)

    llm.chat("SYS", "USR")
    roles = [(m["role"], m["content"]) for m in captured["messages"]]
    assert roles == [("system", "SYS"), ("user", "USR")]
