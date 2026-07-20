"""A minimal API load balancer for Ollama backends (FastAPI + httpx).

WHAT A LOAD BALANCER DOES (in one paragraph):
  It is a reverse proxy that accepts every client request on ONE address and
  forwards it to one of several identical backend servers, spreading the load so
  no single backend is overwhelmed. It also health-checks backends and skips the
  dead ones (failover), so the client sees one stable, always-up endpoint.

DESIGN (kept deliberately simple for learning):
  * Strategy: round-robin — hand each new request to the next backend in turn.
  * Health: a background loop pings /api/tags on every backend every few seconds
    and marks each up/down. Requests only go to healthy backends.
  * Failover: if the chosen backend errors, try the next healthy one.
  * Transparency: we forward the method, path, headers, and body unchanged, so to
    the RAG app the load balancer looks exactly like a single Ollama server.

  Today OLLAMA_BACKENDS has one entry (single server, as requested). Add more
  URLs to that env var and this same code balances across them — no code change.

Run:  uvicorn lb.balancer:app --host 127.0.0.1 --port 8080
"""
from __future__ import annotations

import asyncio
import itertools
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request, Response

from config import settings

# ── Backend registry ───────────────────────────────────────────────────
BACKENDS: list[str] = settings.backend_list
HEALTH: dict[str, bool] = {b: True for b in BACKENDS}   # assume up until first probe
_rr = itertools.cycle(BACKENDS)                          # round-robin cursor
HEALTH_INTERVAL_SECONDS = 5
_client: httpx.AsyncClient | None = None


def _next_healthy() -> list[str]:
    """Return healthy backends starting from the round-robin position.

    We return an ordered list (not a single pick) so the caller can fail over to
    the next candidate if the first one errors mid-request.
    """
    healthy = [b for b in BACKENDS if HEALTH.get(b)]
    if not healthy:
        return []
    # advance the cursor to the next healthy backend for fair spreading
    start = next(_rr)
    while start not in healthy:
        start = next(_rr)
    i = healthy.index(start)
    return healthy[i:] + healthy[:i]


async def _health_loop():
    assert _client is not None
    while True:
        for b in BACKENDS:
            try:
                r = await _client.get(f"{b}/api/tags", timeout=3.0)
                HEALTH[b] = r.status_code == 200
            except Exception:  # noqa: BLE001
                HEALTH[b] = False
        await asyncio.sleep(HEALTH_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _client
    _client = httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=5.0))
    task = asyncio.create_task(_health_loop())
    try:
        yield
    finally:
        task.cancel()
        await _client.aclose()


app = FastAPI(title="Ollama Load Balancer", version="0.1.0", lifespan=lifespan)


@app.get("/lb/health")
async def lb_health():
    """Load-balancer's own status: which backends are up."""
    return {"backends": HEALTH, "healthy_count": sum(HEALTH.values())}


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy(path: str, request: Request):
    """Forward any request to the next healthy backend, with failover."""
    assert _client is not None
    candidates = _next_healthy()
    if not candidates:
        return Response(content="No healthy backends", status_code=503)

    body = await request.body()
    # drop hop-by-hop headers that shouldn't be proxied
    headers = {k: v for k, v in request.headers.items() if k.lower() not in ("host", "content-length")}

    last_status = 502
    for base in candidates:
        url = f"{base}/{path}"
        try:
            resp = await _client.request(
                request.method, url, content=body, headers=headers,
                params=request.query_params,
            )
            return Response(
                content=resp.content,
                status_code=resp.status_code,
                headers={k: v for k, v in resp.headers.items()
                         if k.lower() not in ("content-length", "transfer-encoding", "connection")},
            )
        except Exception:  # noqa: BLE001 - mark down, try next candidate
            HEALTH[base] = False
            last_status = 502
            continue
    return Response(content="All backends failed", status_code=last_status)
