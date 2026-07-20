# 02 — Setup & Run

Target machine: macOS on Apple Silicon (16 GB). Everything is local and free.

## Prerequisites

1. **Python 3.9+** (already present on macOS; a newer 3.11+ is fine too).
2. **Ollama** — the local LLM server. Install from https://ollama.com/download
   (or `brew install ollama`). It runs the generation model on the Metal GPU.

## One-time setup

```bash
cd ~/Projects/cbx-rag
./scripts/setup.sh
```

This will:
1. create the `.venv` virtual environment,
2. install Python dependencies from `requirements.txt`,
3. copy `.env.example` → `.env`,
4. `ollama pull qwen2.5:7b` (~4.7 GB download, one time).

If Ollama isn't installed yet, the script tells you and you can pull the model
later with `ollama pull qwen2.5:7b`.

## First run — sample docs (do this before CBX data)

```bash
source .venv/bin/activate

# 1. index the tiny sample corpus
python scripts/ingest_docs.py sample_docs/

# 2. prove retrieval works WITHOUT the LLM (fast, offline)
python -m pytest tests/ -v

# 3. start the load balancer + RAG API
./scripts/run_all.sh
```

Open http://127.0.0.1:8000/docs for the interactive API, or:

```bash
# retrieval only (no LLM) — great for checking recall
curl -s http://127.0.0.1:8000/search \
  -H 'content-type: application/json' \
  -d '{"query":"why do I get a 401?"}' | python3 -m json.tool

# full grounded answer (needs Ollama running)
curl -s http://127.0.0.1:8000/ask \
  -H 'content-type: application/json' \
  -d '{"question":"What order do I onboard a new tenant in?"}' | python3 -m json.tool
```

## Ports

| Service | URL |
|---|---|
| RAG API | http://127.0.0.1:8000 (`/docs`, `/ask`, `/search`, `/health`) |
| Load balancer | http://127.0.0.1:8080 (`/lb/health`) |
| Ollama | http://127.0.0.1:11434 (started by Ollama itself) |

## Troubleshooting

- **`/ask` errors but `/search` works** → the LLM path is down. Check Ollama is
  running (`ollama list`) and the LB health at http://127.0.0.1:8080/lb/health.
- **First `/ask` is slow** → the model is loading into memory; subsequent calls
  are fast.
- **Empty or poor answers** → check `/search` first. If retrieval is wrong, the
  LLM can't help — tune `CHUNK_SIZE`, `CHUNK_OVERLAP`, `TOP_K` in `.env` and
  re-ingest with `--reset`.
- **Torch/deps install slow** → it's downloading PyTorch (large); one time only.
