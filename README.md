# cbx-rag

A local, fully-free Retrieval-Augmented Generation (RAG) system for CBX /
TradeBeyond documentation and support. Built in Python, runs on a single machine,
no paid APIs.

The system answers natural-language questions **only from your documentation**,
citing the source files — so it can help onboard engineers, assist support
ticket handling, and answer "how does X work in CBX" without hallucinating.

---

## Architecture (single server, for now)

```
                        ┌──────────────────────────────────────────┐
   Your question  ─────▶│  RAG API  (FastAPI, :8000)                │
                        │                                           │
                        │  1. embed the question   (bge-small)      │
                        │  2. search vector store  (Chroma)         │
                        │  3. build grounded prompt with top-k docs │
                        │  4. ask the LLM ──────────┐               │
                        └───────────────────────────┼───────────────┘
                                                     ▼
                        ┌──────────────────────────────────────────┐
                        │  Load Balancer (FastAPI, :8080)           │
                        │  round-robin + health-check + failover    │
                        └───────────────────────────┼───────────────┘
                                                     ▼
                        ┌──────────────────────────────────────────┐
                        │  Ollama backend(s) (:11434)               │
                        │  Qwen2.5-7B-Instruct  (generation LLM)    │
                        └──────────────────────────────────────────┘
```

- **Embedding model:** `BAAI/bge-small-en-v1.5` (Hugging Face, ~130 MB, CPU)
- **Vector store:** Chroma (persistent, local, no server)
- **Generation LLM:** `qwen2.5:7b` via Ollama (uses Apple Metal GPU)
- **Load balancer:** custom FastAPI reverse proxy (1 backend today, N-ready)

See [`docs/01-architecture.md`](docs/01-architecture.md) for the full picture.

---

## Quick start

```bash
# 1. one-time setup (venv, deps, .env, pull the LLM)
./scripts/setup.sh

# 2. ingest the sample docs first (proves the pipeline)
source .venv/bin/activate
python scripts/ingest_docs.py sample_docs/

# 3. run the test suite (38 tests, no Ollama needed — LLM is mocked)
pip install -r requirements-dev.txt
python -m pytest

# 4. start everything
./scripts/run_all.sh

# 5. ask a question
curl -s http://127.0.0.1:8000/ask \
  -H 'content-type: application/json' \
  -d '{"question": "Why do I get a 401 error?"}' | python3 -m json.tool
```

Once the sample docs work, point ingestion at the real CBX docs:

```bash
python scripts/ingest_docs.py ../cbx-playwright/TRADEBEYOND_KNOWLEDGE_BASE.md --reset
python scripts/ingest_docs.py ../cbx-playwright/CBX_API_HANDOUT.md
```

---

## Project layout

| Path | What it is |
|---|---|
| `config.py` | All settings (env-overridable via `.env`) |
| `app/embeddings.py` | bge-small embedding wrapper |
| `app/ingest.py` | Document loading + chunking (.md/.txt/.pdf/.docx) |
| `app/vectorstore.py` | Chroma add/query/reset |
| `app/llm.py` | Ollama chat client (via the load balancer) |
| `app/rag.py` | Retrieve → grounded prompt → generate |
| `app/api.py` | RAG HTTP API (`/ask`, `/search`, `/health`) |
| `lb/balancer.py` | The API load balancer |
| `scripts/` | setup, ingest, run-all |
| `sample_docs/` | Simple docs to test with first |
| `tests/` | No-LLM smoke tests for retrieval |
| `docs/` | Full written documentation + changelog |

---

## Documentation

- [`docs/01-architecture.md`](docs/01-architecture.md) — components and data flow
- [`docs/02-setup.md`](docs/02-setup.md) — install & run, step by step
- [`docs/03-how-rag-works.md`](docs/03-how-rag-works.md) — RAG explained
- [`docs/04-load-balancer.md`](docs/04-load-balancer.md) — how the LB works & how to scale
- [`docs/05-cbx-data.md`](docs/05-cbx-data.md) — moving from sample docs to CBX data
- [`docs/06-conversation-memory.md`](docs/06-conversation-memory.md) — multi-turn memory + strict grounding
- [`docs/07-tickets.md`](docs/07-tickets.md) — support tickets + agent-assist
- [`docs/CHANGELOG.md`](docs/CHANGELOG.md) — what changed, when
