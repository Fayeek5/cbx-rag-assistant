# Deploying to Render

This project runs fully locally with Ollama. To host it as a public web service
on [Render](https://render.com), two things change: the local LLM is replaced by
a hosted **OpenAI-compatible** endpoint, and the vector store lives on a Render
persistent disk. The repo ships a `render.yaml` blueprint that wires all of this.

## What changes vs. local

| | Local | Render |
|---|---|---|
| LLM | Ollama (`qwen2.5:7b`) via the load balancer | Hosted API (`LLM_PROVIDER=openai`) |
| Vector store | `./data/chroma_db` | `/var/data/chroma_db` (persistent disk) |
| Reranker | on | off by default (saves memory) |
| Served on | `127.0.0.1:8000` | `0.0.0.0:$PORT` |

The retrieval pipeline (embeddings, Chroma, BM25) is unchanged — only generation
moves to a hosted model.

## Prerequisites

1. A **Render** account (free to sign up).
2. An **OpenAI-compatible API key** from any of these providers:
   - **Groq** — free tier, fast, OpenAI-compatible. Base URL
     `https://api.groq.com/openai/v1`, e.g. model `llama-3.1-8b-instant`.
   - **OpenRouter** — `https://openrouter.ai/api/v1`, many models.
   - **OpenAI** — `https://api.openai.com/v1`, e.g. `gpt-4o-mini`.

   The blueprint defaults to Groq; change `OPENAI_BASE_URL` / `LLM_MODEL` for others.

## Deploy steps

1. Push this repo to GitHub (already done for `cbx-rag-assistant`).
2. In Render: **New → Blueprint**, pick this repository. Render reads
   `render.yaml` and creates the web service + disk.
3. When prompted, set the one secret it can't read from the file:
   **`OPENAI_API_KEY`** = your provider key.
4. Click **Apply**. First deploy installs deps, then the start script seeds the
   vector store from `sample_docs/` on the persistent disk (once).
5. When the health check at `/health` passes, open the service URL — the chat UI
   is at `/`.

## Sizing (read this)

The embedding model pulls in `torch` + `sentence-transformers`, which need real
memory at runtime:

- **Recommended: the `standard` plan (2 GB)** — reliable.
- The **512 MB free/starter tiers will likely OOM** on model load, even with the
  reranker off. You can try, but expect restarts.
- The blueprint sets `USE_RERANKER=false` to cut memory; hybrid retrieval
  (vector + BM25) still runs. Turn it back on (`USE_RERANKER=true`) only on a
  larger instance.

## Using your own docs instead of the samples

Edit the ingest line in `scripts/render_start.sh` to point at your docs, or SSH
into the instance and run:

```bash
python scripts/ingest_docs.py path/to/your-docs/ --reset
rm /var/data/chroma_db/.seeded   # allow a fresh re-seed on next boot if desired
```

## A note on Vercel

Vercel is serverless and can't hold the embedding model / Chroma in memory
between requests, so it isn't a fit for this Python backend. Use it only if you
split out a static frontend; the API belongs on Render (or any container host).
