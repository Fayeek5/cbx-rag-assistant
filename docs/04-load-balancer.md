# 04 — The API Load Balancer

## What a load balancer is

A load balancer is a **reverse proxy**: clients send every request to one stable
address, and it forwards each request to one of several identical backend servers.
It exists to:

1. **Spread load** so no single backend is overwhelmed (higher throughput).
2. **Provide failover** — if a backend is down, route around it, so the client
   sees one always-up endpoint.
3. **Decouple** clients from how many backends exist or where they live.

In our stack it sits between the RAG app and Ollama:

```
RAG app ──▶ Load Balancer (:8080) ──┬──▶ Ollama backend A (:11434)
                                    ├──▶ Ollama backend B (:11435)   (future)
                                    └──▶ Ollama backend C (other host) (future)
```

Today there is **one** backend (single server, as requested). The balancer is
still in the path so the design is correct and scaling later is a config change,
not a rewrite.

## How ours works (`lb/balancer.py`)

It's a small FastAPI app with three responsibilities:

### 1. Round-robin selection
A `itertools.cycle` cursor hands each new request to the next backend in turn, so
load is spread evenly. `_next_healthy()` returns the healthy backends ordered
starting from the current cursor position.

### 2. Health checking
A background task (`_health_loop`) pings every backend's `/api/tags` endpoint
every 5 seconds and records up/down in the `HEALTH` dict. Only healthy backends
receive traffic. Check it live:

```bash
curl -s http://127.0.0.1:8080/lb/health | python3 -m json.tool
# {"backends": {"http://127.0.0.1:11434": true}, "healthy_count": 1}
```

### 3. Transparent proxy with failover
The catch-all route forwards the method, path, query string, headers, and body
unchanged to the chosen backend. If that backend errors, it marks it down and
tries the next healthy one. To the RAG app, the balancer is indistinguishable
from a single Ollama server — same `/api/chat` contract.

## How to scale to multiple backends

No code changes. Two options:

**A. More models/instances on the same Mac** (different ports):
```bash
OLLAMA_HOST=127.0.0.1:11435 ollama serve &   # second instance
```
Then in `.env`:
```
OLLAMA_BACKENDS=http://127.0.0.1:11434,http://127.0.0.1:11435
```

**B. Backends on other machines:**
```
OLLAMA_BACKENDS=http://127.0.0.1:11434,http://192.168.1.50:11434
```

Restart the load balancer and it round-robins across all of them, health-checking
each.

## Limitations (intentional, Phase 1)

- **Round-robin only** — no "least connections" or latency-aware routing. Fine
  for identical local backends; revisit if backends differ in speed.
- **No request queuing / concurrency cap** — a real production LB would bound the
  in-flight requests per backend. Add later if needed.
- **No TLS/auth** — it binds to localhost only. Don't expose it to a network
  without adding authentication and HTTPS first.
