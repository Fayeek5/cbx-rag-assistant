"""LLM client.

Talks to the API load balancer (which forwards to one or more Ollama backends)
using Ollama's /api/chat endpoint. If the load balancer is down we fall back to
the first backend directly, so the RAG app still works before the LB is running.
"""
from __future__ import annotations

import httpx

from config import settings

_TIMEOUT = httpx.Timeout(120.0, connect=5.0)


def chat(system: str, user: str, model: str | None = None) -> str:
    """Send a system+user prompt, return the assistant's text."""
    payload = {
        "model": model or settings.llm_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
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
