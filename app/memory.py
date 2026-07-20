"""In-process conversation memory (per session).

Keeps the last N turns of each chat so the assistant can resolve follow-ups
("the second one", "why does that happen?"). Deliberately simple and local:
an in-memory dict, capped per session. Memory is NOT persisted — it resets when
the server restarts, which is fine for a single-server local tool. For a
multi-worker or persistent deployment, back this with Redis or a DB.
"""
from __future__ import annotations

import threading
from collections import deque

from config import settings

_lock = threading.Lock()
# session_id -> deque[{"role": "user"|"assistant", "content": str}]
_store: dict[str, deque] = {}


def _maxlen() -> int:
    # store user+assistant messages, so 2x the number of turns
    return settings.history_turns * 2


def get_history(session_id: str) -> list[dict]:
    """Return prior turns for a session, oldest first (empty if none)."""
    if not session_id:
        return []
    with _lock:
        dq = _store.get(session_id)
        return list(dq) if dq else []


def append(session_id: str, role: str, content: str) -> None:
    if not session_id:
        return
    with _lock:
        dq = _store.get(session_id)
        if dq is None:
            dq = deque(maxlen=_maxlen())
            _store[session_id] = dq
        dq.append({"role": role, "content": content})


def reset(session_id: str) -> None:
    with _lock:
        _store.pop(session_id, None)
