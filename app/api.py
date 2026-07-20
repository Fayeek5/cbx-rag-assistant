"""RAG HTTP API (FastAPI).

Endpoints:
  GET  /health           -> liveness + how many chunks are indexed
  POST /ask   {question} -> grounded answer + sources + retrieved passages
  POST /search {query}   -> retrieval only (no LLM), useful for debugging recall

Run:  uvicorn app.api:app --host 127.0.0.1 --port 8000
"""
from __future__ import annotations

import os
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel

from config import settings
from app import vectorstore, memory
from app.rag import answer

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


@app.post("/reset")
def reset(req: ResetRequest):
    """Clear a conversation's memory (New chat)."""
    memory.reset(req.session_id)
    return {"status": "ok", "session_id": req.session_id}


@app.post("/search")
def search(req: SearchRequest):
    return {"results": vectorstore.query(req.query, top_k=req.top_k)}
