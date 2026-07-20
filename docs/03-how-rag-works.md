# 03 — How RAG Works (and how ours is built)

## The problem RAG solves

A plain LLM only knows what it was trained on. It doesn't know your CBX API
quirks, your onboarding order, or last month's resolved tickets — and if you ask
anyway, it will confidently invent an answer. RAG fixes this by **retrieving
your documents at question time and making the model answer from them**.

## The pipeline, step by step

### 1. Ingestion (done once, ahead of time)

**Load** each file to plain text (`app/ingest.py`, `.md/.txt/.pdf/.docx`).

**Chunk** the text into ~800-character passages with ~120 characters of overlap.
Why chunk?
- An embedding vector represents one focused idea well, a whole document poorly.
- Retrieval returns *chunks*, so smaller chunks = more precise citations.
- Overlap keeps a sentence that straddles a boundary findable in both chunks.

We chunk on paragraph boundaries so we don't cut mid-sentence. Section-aware
chunking (splitting on Markdown headings) is a natural future improvement — see
`docs/05-cbx-data.md`.

**Embed** each chunk with bge-small into a 384-dimension vector that captures
meaning. Two texts about the same thing land close together in vector space even
if they share no words.

**Store** each `(vector, text, source)` in Chroma on disk.

### 2. Query (every question)

**Embed the question** the same way (bge adds a short "search" prefix to queries
only — a quirk of bge models that measurably improves recall).

**Search** Chroma for the `top_k` (default 5) nearest chunks by cosine
similarity. This is an *approximate* nearest-neighbour search (HNSW index) — near
instant even over large corpora.

**Build a grounded prompt** (`app/rag.py`): the retrieved passages are numbered
and inserted into the prompt, and the system prompt says *answer only from these,
cite sources, and say "I don't have that" otherwise*.

**Generate** with Qwen2.5-7B via Ollama. Temperature is low (0.1) so the model
stays faithful to the passages rather than being creative.

**Return** `{answer, sources, passages}` — the passages are included so a human
(or a test) can audit exactly what the answer was based on.

## Why retrieval quality dominates

If the right passage isn't retrieved, the LLM literally cannot answer correctly —
it will either guess or say "I don't have that." So debug retrieval first, using
the `/search` endpoint (no LLM involved). If `/search` returns the right chunk,
the answer will almost always be good. If it doesn't, tune:

| Knob (`.env`) | Effect |
|---|---|
| `CHUNK_SIZE` | Smaller = more precise but more fragmented; larger = more context per hit |
| `CHUNK_OVERLAP` | More overlap = fewer boundary misses, slightly more storage |
| `TOP_K` | More passages = higher recall but longer prompt (slower, costlier tokens) |
| `EMBEDDING_MODEL` | Upgrade to `bge-base-en-v1.5` for better recall if RAM allows |

Re-ingest with `--reset` after changing chunking knobs.

## What this design deliberately does NOT do (yet)

- **Re-ranking**: a second, more precise model to reorder the top-k. Easy to add
  later for a quality bump.
- **Streaming answers**: responses come back whole, not token-by-token.
- **Conversation memory**: each question is independent. Add history in `app/rag.py`.
- **Section-aware chunking**: currently paragraph-based, not heading-based.

These are intentional Phase-1 simplifications, documented so we know what's next.
