"""Lightweight request logging + metrics (local, file-based).

Every answered turn is appended to data/requests.jsonl (one JSON object per line).
The /metrics endpoint reads that file and returns aggregates — refusal rate,
average latency, intent breakdown, most-cited sources, recent questions — so you
can see how the assistant is actually being used and where it's failing/ slow.

Sensitive text is redacted (via app.security) before it is written.
"""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone

from app.security import redact

_LOCK = threading.Lock()
_LOG_PATH = os.path.join("data", "requests.jsonl")


def log_turn(*, session_id: str, question: str, intent: str, answer: str,
             sources: list[str], top_score: float | None, latency_ms: int,
             refused: bool) -> None:
    """Append one turn to the request log (best-effort; never raises)."""
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id or None,
        "question": redact(question),
        "intent": intent,
        "answer": redact(answer),
        "sources": [s.split("/")[-1] for s in (sources or [])],
        "top_score": round(top_score, 4) if top_score is not None else None,
        "latency_ms": latency_ms,
        "refused": refused,
    }
    try:
        with _LOCK:
            os.makedirs("data", exist_ok=True)
            with open(_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
    except Exception:  # noqa: BLE001 - telemetry must never break a request
        pass


def _read() -> list[dict]:
    if not os.path.exists(_LOG_PATH):
        return []
    out = []
    with open(_LOG_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except Exception:  # noqa: BLE001
                    continue
    return out


def metrics(recent: int = 10) -> dict:
    """Aggregate stats over the whole request log."""
    rows = _read()
    n = len(rows)
    if not n:
        return {"total_requests": 0}

    doc_rows = [r for r in rows if r.get("intent") == "doc"]
    refused = sum(1 for r in doc_rows if r.get("refused"))
    latencies = [r["latency_ms"] for r in rows if isinstance(r.get("latency_ms"), int)]
    latencies.sort()

    def pct(p):
        if not latencies:
            return None
        i = min(len(latencies) - 1, int(p / 100 * len(latencies)))
        return latencies[i]

    intents: dict[str, int] = {}
    for r in rows:
        intents[r.get("intent", "?")] = intents.get(r.get("intent", "?"), 0) + 1

    src_counts: dict[str, int] = {}
    for r in rows:
        for s in r.get("sources", []):
            src_counts[s] = src_counts.get(s, 0) + 1
    top_sources = sorted(src_counts.items(), key=lambda kv: kv[1], reverse=True)[:5]

    return {
        "total_requests": n,
        "doc_questions": len(doc_rows),
        "refusals": refused,
        "refusal_rate": round(refused / len(doc_rows), 3) if doc_rows else None,
        "latency_ms": {"avg": round(sum(latencies) / len(latencies)) if latencies else None,
                        "p50": pct(50), "p95": pct(95)},
        "intents": intents,
        "top_sources": [{"source": s, "count": c} for s, c in top_sources],
        "recent": [{"q": r.get("question"), "intent": r.get("intent"),
                    "refused": r.get("refused"), "ms": r.get("latency_ms")}
                   for r in rows[-recent:]][::-1],
    }
