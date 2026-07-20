# 01 — Architecture

## Goal

Answer questions about CBX / TradeBeyond using our own documentation, locally,
with no paid services, and without the model making things up.

## The two halves of RAG

RAG = **Retrieval** + **Generation**.

1. **Retrieval** finds the handful of documentation passages most relevant to a
   question. This half determines whether the right facts even reach the model.
   Most RAG quality problems live here.
2. **Generation** is the LLM writing an answer using only those passages.

## Components

| Component | Technology | Why this choice |
|---|---|---|
| Embedding model | `BAAI/bge-small-en-v1.5` | Small (130 MB), fast on CPU, strong retrieval quality. Free from Hugging Face. |
| Vector store | Chroma (persistent) | Local, single-file DB, no separate server, built-in HNSW ANN index. |
| Generation LLM | `qwen2.5:7b` (Ollama) | Best quality/size balance that fits in 16 GB; Ollama uses the Mac's Metal GPU. Free. |
| Load balancer | FastAPI + httpx | Single stable endpoint in front of the LLM backend(s); ready to scale to N backends. |
| APIs | FastAPI + uvicorn | Simple, async, auto-generated `/docs` UI. |

## Data flow (query time)

```
question
   │
   ▼
embed_query()                      app/embeddings.py   (bge-small + search prefix)
   │  vector
   ▼
vectorstore.query() top-k          app/vectorstore.py  (Chroma cosine search)
   │  passages (text + source)
   ▼
rag.answer(): build grounded prompt app/rag.py
   │  system + user prompt
   ▼
llm.chat()  ──▶ Load Balancer ──▶ Ollama ──▶ Qwen2.5-7B
   │  answer text
   ▼
{answer, sources, passages}         returned by app/api.py  /ask
```

## Data flow (ingestion time)

```
file (.md/.txt/.pdf/.docx)
   │
   ▼
load_file() → raw text              app/ingest.py
   │
   ▼
chunk_text() → overlapping chunks   app/ingest.py
   │
   ▼
embed_passages()                    app/embeddings.py
   │  vectors
   ▼
vectorstore.add_chunks()            app/vectorstore.py  → Chroma on disk
```

## Why the anti-hallucination guardrail matters

The system prompt in `app/rag.py` forces the model to answer **only** from the
retrieved passages and to say *"I don't have that in the documentation."* when
the answer isn't present. For CBX support this is the whole point: a confident
wrong answer is worse than "I don't know." Every answer also lists its source
files so a human can verify.

## Deployment scope

- **Now:** everything on one machine. One Ollama backend. The load balancer
  still sits in the path so the architecture is correct from day one.
- **Later:** add more Ollama backends (same machine on different ports, or other
  machines) by editing `OLLAMA_BACKENDS` in `.env` — no code change.
