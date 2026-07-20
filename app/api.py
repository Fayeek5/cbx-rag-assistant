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
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from config import settings
from app import vectorstore, memory
from app.rag import answer, answer_stream

app = FastAPI(title="CBX RAG API", version="0.1.0")

_CHAT_HTML = os.path.join(os.path.dirname(__file__), "static", "chat.html")


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
    result = answer(req.question, session_id=req.session_id or "", top_k=req.top_k)
    result["session_id"] = req.session_id
    return result


@app.post("/ask/stream")
def ask_stream(req: AskRequest):
    """Streaming variant: Server-Sent Events. Emits token deltas, then a final
    'meta' event with sources/passages/intent/followups."""
    def gen():
        try:
            for ev in answer_stream(req.question, session_id=req.session_id or "", top_k=req.top_k):
                yield f"data: {json.dumps(ev)}\n\n"
        except Exception as e:  # noqa: BLE001
            yield f"data: {json.dumps({'type': 'error', 'text': str(e)})}\n\n"
        yield "data: {\"type\": \"done\"}\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


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
