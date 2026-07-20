"""RAG HTTP API (FastAPI).

Endpoints:
  GET  /health           -> liveness + how many chunks are indexed
  POST /ask   {question} -> grounded answer + sources + retrieved passages
  POST /search {query}   -> retrieval only (no LLM), useful for debugging recall

Run:  uvicorn app.api:app --host 127.0.0.1 --port 8000
"""
from __future__ import annotations

from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel

from config import settings
from app import vectorstore
from app.rag import answer

app = FastAPI(title="CBX RAG API", version="0.1.0")


class AskRequest(BaseModel):
    question: str
    top_k: Optional[int] = None


class SearchRequest(BaseModel):
    query: str
    top_k: Optional[int] = None


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
    return answer(req.question, top_k=req.top_k)


@app.post("/search")
def search(req: SearchRequest):
    return {"results": vectorstore.query(req.query, top_k=req.top_k)}
