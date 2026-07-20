# Changelog

All notable changes to cbx-rag are recorded here. Newest first.

## [0.1.0] — 2026-07-20 — Phase 1 scaffold

Initial local, single-server RAG stack. Free/local throughout (no paid APIs).

### Added
- **Project scaffold**: `config.py` (env-overridable settings), `requirements.txt`,
  `.gitignore`, `.env.example`.
- **RAG pipeline** (`app/`):
  - `embeddings.py` — `BAAI/bge-small-en-v1.5` via sentence-transformers (CPU),
    with the bge query prefix.
  - `ingest.py` — loaders for `.md/.txt/.pdf/.docx` + paragraph chunking with
    overlap.
  - `vectorstore.py` — Chroma persistent store (cosine), add/query/reset;
    telemetry disabled.
  - `llm.py` — Ollama `/api/chat` client that goes through the load balancer with
    direct-backend fallback.
  - `rag.py` — retrieve → grounded prompt (anti-hallucination system prompt) →
    generate.
  - `api.py` — FastAPI app: `/health`, `/ask`, `/search`.
- **Load balancer** (`lb/balancer.py`) — FastAPI reverse proxy over Ollama
  backends: round-robin, background health checks, failover. Single backend by
  default, N-backend ready via `OLLAMA_BACKENDS`.
- **Scripts**: `setup.sh` (venv/deps/env/model pull), `ingest_docs.py` (CLI
  ingestion with `--reset`), `run_all.sh` (start LB + API).
- **Sample docs** (`sample_docs/`) — widget API + onboarding, to test the
  pipeline before CBX data.
- **Smoke tests** (`tests/test_smoke.py`) — chunking + retrieval, no LLM/network.
- **Documentation** (`docs/`) — architecture, setup, how-RAG-works, load-balancer,
  cbx-data, this changelog.

### Verified
- Dependencies install cleanly in `.venv` (Python 3.9).
- Smoke test passes: chunking OK; retrieval returns the correct chunk
  ("401 Unauthorized", score 0.781) — the retrieval half of RAG works end to end.

### Decisions
- **Generation LLM: `qwen2.5:7b` via Ollama** — best quality/size for 16 GB Apple
  Silicon; Ollama uses the Metal GPU.
- **Embeddings: `bge-small-en-v1.5`** — small, fast on CPU, strong recall.
- **Vector store: Chroma** — local, persistent, no separate server.
- **Load balancer kept in the path even with one backend** so scaling later is a
  config change, not a rewrite.

### Known limitations / next up
- Paragraph chunking, not section-aware (see `docs/05-cbx-data.md`).
- No re-ranking, no streaming, no conversation memory (Phase 2 candidates).
- LB is round-robin only, localhost only, no auth/TLS.

### Pending
- Verify full `/ask` path against a running Ollama (requires `ollama pull qwen2.5:7b`).
- Create the private GitHub repo and push (blocked on `gh auth login`).
- Ingest the real CBX corpus and validate retrieval quality.
