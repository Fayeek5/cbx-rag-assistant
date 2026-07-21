"""RAG HTTP API (FastAPI).

Endpoints:
  GET  /health           -> liveness + how many chunks are indexed
  POST /ask   {question} -> grounded answer + sources + retrieved passages
  POST /search {query}   -> retrieval only (no LLM), useful for debugging recall

Run:  uvicorn app.api:app --host 127.0.0.1 --port 8000
"""
from __future__ import annotations

import json
import os
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from pydantic import BaseModel

from config import settings
from app import vectorstore, memory, telemetry
from app.rag import answer, answer_stream, assist, REFUSAL
from app.connectors import REGISTRY, get_connector
from app.tickets import tickets_to_chunks

app = FastAPI(title="CBX RAG API", version="0.1.0")

_CHAT_HTML = os.path.join(os.path.dirname(__file__), "static", "chat.html")

MAX_QUESTION_CHARS = 2000
_RATE_MAX = 30          # max requests
_RATE_WINDOW = 60.0     # per this many seconds, per client IP
_hits: dict[str, deque] = defaultdict(deque)


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    """Simple in-memory sliding-window rate limit on the answer endpoints."""
    if request.url.path in ("/ask", "/ask/stream"):
        ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        dq = _hits[ip]
        while dq and now - dq[0] > _RATE_WINDOW:
            dq.popleft()
        if len(dq) >= _RATE_MAX:
            return JSONResponse({"detail": "Rate limit exceeded. Try again shortly."}, status_code=429)
        dq.append(now)
    return await call_next(request)


def _too_long(question: str) -> bool:
    return len(question or "") > MAX_QUESTION_CHARS


def _log(session_id, question, result, latency_ms):
    passages = result.get("passages") or []
    telemetry.log_turn(
        session_id=session_id or "", question=question,
        intent=result.get("intent", "doc"), answer=result.get("answer", ""),
        sources=result.get("sources", []),
        top_score=(passages[0].get("score") if passages else None),
        latency_ms=latency_ms,
        refused=result.get("answer", "").strip().startswith(REFUSAL.rstrip(".")),
    )


@app.get("/")
def chat_ui():
    """Serve the chat UI (single self-contained page)."""
    return FileResponse(_CHAT_HTML)


class AskRequest(BaseModel):
    question: str
    session_id: Optional[str] = None   # groups turns into one conversation
    top_k: Optional[int] = None


class SearchRequest(BaseModel):
    query: str
    top_k: Optional[int] = None


class ResetRequest(BaseModel):
    session_id: str


class FeedbackRequest(BaseModel):
    session_id: Optional[str] = None
    question: str
    answer: str
    rating: str          # "up" | "down"
    comment: Optional[str] = None


@app.get("/health")
def health():
    return {
        "status": "ok",
        "indexed_chunks": vectorstore.count(),
        "embedding_model": settings.embedding_model,
        "llm_model": settings.llm_model,
    }


@app.post("/ask")
def ask(req: AskRequest):
    if _too_long(req.question):
        return JSONResponse({"detail": f"Question too long (max {MAX_QUESTION_CHARS} chars)."}, status_code=400)
    t0 = time.monotonic()
    result = answer(req.question, session_id=req.session_id or "", top_k=req.top_k)
    _log(req.session_id, req.question, result, int((time.monotonic() - t0) * 1000))
    result["session_id"] = req.session_id
    return result


@app.post("/ask/stream")
def ask_stream(req: AskRequest):
    """Streaming variant: Server-Sent Events. Emits token deltas, then a final
    'meta' event with sources/passages/intent/followups."""
    if _too_long(req.question):
        return JSONResponse({"detail": f"Question too long (max {MAX_QUESTION_CHARS} chars)."}, status_code=400)

    def gen():
        t0 = time.monotonic()
        acc, meta = "", None
        try:
            for ev in answer_stream(req.question, session_id=req.session_id or "", top_k=req.top_k):
                if ev.get("type") == "token":
                    acc += ev.get("text", "")
                elif ev.get("type") == "meta":
                    meta = ev
                yield f"data: {json.dumps(ev)}\n\n"
        except Exception as e:  # noqa: BLE001
            yield f"data: {json.dumps({'type': 'error', 'text': str(e)})}\n\n"
        if meta is not None:
            result = {"answer": acc, "sources": meta.get("sources", []),
                      "passages": meta.get("passages", []), "intent": meta.get("intent", "doc")}
            _log(req.session_id, req.question, result, int((time.monotonic() - t0) * 1000))
        yield "data: {\"type\": \"done\"}\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/metrics")
def get_metrics():
    """Usage + health aggregates from the request log."""
    return telemetry.metrics()


class AssistRequest(BaseModel):
    ticket: str
    top_k: Optional[int] = None


@app.post("/assist")
def assist_endpoint(req: AssistRequest):
    """Agent-assist: draft a grounded triage for a support engineer from similar
    resolved tickets + docs."""
    if _too_long(req.ticket):
        return JSONResponse({"detail": f"Ticket too long (max {MAX_QUESTION_CHARS} chars)."}, status_code=400)
    return assist(req.ticket, top_k=req.top_k)


# ── Ticket connectors ────────────────────────────────────────────────────
class SyncRequest(BaseModel):
    limit: Optional[int] = 100
    dry_run: bool = False


@app.get("/connectors")
def list_connectors():
    """List ticket connectors with their configured status (no secrets exposed)."""
    out = []
    for name in REGISTRY:
        err = get_connector(name).check_config()
        out.append({"name": name, "configured": err is None, "message": err})
    return {"connectors": out}


@app.post("/connectors/{name}/sync")
def sync_connector(name: str, req: SyncRequest):
    """Fetch resolved tickets from a source and ingest them (or dry-run preview)."""
    try:
        conn = get_connector(name)
    except ValueError as e:
        return JSONResponse({"detail": str(e)}, status_code=404)
    err = conn.check_config()
    if err:
        return JSONResponse({"detail": err}, status_code=400)
    try:
        tickets = conn.fetch(limit=req.limit)
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"detail": f"Fetch failed: {e}"}, status_code=502)
    if req.dry_run:
        return {"fetched": len(tickets), "ingested": 0, "dry_run": True,
                "sample": [{"id": t.get("id"), "summary": t.get("summary")} for t in tickets[:5]]}
    added = vectorstore.add_chunks(tickets_to_chunks(tickets))
    return {"fetched": len(tickets), "ingested": added, "total_chunks": vectorstore.count()}


@app.post("/reset")
def reset(req: ResetRequest):
    """Clear a conversation's memory (New chat)."""
    memory.reset(req.session_id)
    return {"status": "ok", "session_id": req.session_id}


@app.post("/feedback")
def feedback(req: FeedbackRequest):
    """Log thumbs up/down to data/feedback.jsonl — seeds a future eval set."""
    os.makedirs("data", exist_ok=True)
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "session_id": req.session_id,
        "question": req.question,
        "answer": req.answer,
        "rating": req.rating,
        "comment": req.comment,
    }
    with open(os.path.join("data", "feedback.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    return {"status": "ok"}


@app.post("/search")
def search(req: SearchRequest):
    return {"results": vectorstore.query(req.query, top_k=req.top_k)}
