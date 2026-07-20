"""LLM client.

Talks to the API load balancer (which forwards to one or more Ollama backends)
using Ollama's /api/chat endpoint. If the load balancer is down we fall back to
the first backend directly, so the RAG app still works before the LB is running.
"""
from __future__ import annotations

import json
from typing import Iterator

import httpx

from config import settings

_TIMEOUT = httpx.Timeout(120.0, connect=5.0)


def chat_messages(messages: list[dict], model: str | None = None) -> str:
    """Send a full messages list (system/user/assistant turns), return the text.

    Tries the load balancer first, then each backend directly as failover.
    """
    payload = {
        "model": model or settings.llm_model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": 0.1},  # low temp = faithful, less invention
    }

    targets = [settings.lb_url] + settings.backend_list  # LB first, then direct
    last_err: Exception | None = None
    for base in targets:
        try:
            r = httpx.post(f"{base}/api/chat", json=payload, timeout=_TIMEOUT)
            r.raise_for_status()
            return r.json()["message"]["content"]
        except Exception as e:  # noqa: BLE001 - try next target
            last_err = e
            continue
    raise RuntimeError(f"All LLM targets failed. Last error: {last_err}")


def chat(system: str, user: str, model: str | None = None) -> str:
    """Convenience single-turn wrapper around chat_messages()."""
    return chat_messages(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        model=model,
    )


def chat_messages_stream(messages: list[dict], model: str | None = None) -> Iterator[str]:
    """Yield answer text deltas as Ollama generates them (stream=True).

    Ollama's /api/chat returns JSON lines; each carries a partial
    message.content and a final {"done": true}. Same LB-then-backend failover.
    """
    payload = {
        "model": model or settings.llm_model,
        "messages": messages,
        "stream": True,
        "options": {"temperature": 0.1},
    }
    targets = [settings.lb_url] + settings.backend_list
    last_err: Exception | None = None
    for base in targets:
        try:
            with httpx.stream("POST", f"{base}/api/chat", json=payload, timeout=_TIMEOUT) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if not line:
                        continue
                    obj = json.loads(line)
                    delta = obj.get("message", {}).get("content", "")
                    if delta:
                        yield delta
                    if obj.get("done"):
                        return
            return
        except Exception as e:  # noqa: BLE001 - try next target
            last_err = e
            continue
    raise RuntimeError(f"All LLM targets failed (stream). Last error: {last_err}")
