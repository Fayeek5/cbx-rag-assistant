# Changelog

All notable changes to cbx-rag are recorded here. Newest first.

## [0.5.0] — 2026-07-20 — Full test suite + loading-UX fix

### Added
- **Automated test suite (38 tests, pytest)** — all green in ~8s, LLM mocked so
  no Ollama/network needed:
  - `test_ingest.py` — chunking, size limits, loaders, file discovery
  - `test_embeddings.py` — shape, L2 normalization, semantic ordering (real bge-small)
  - `test_vectorstore.py` — add/query/count/reset, upsert idempotency, top-k
  - `test_memory.py` — append/get, per-session isolation, history cap, reset
  - `test_rag.py` — answer cleaning, refusal→no sources, memory wiring, condense
  - `test_llm.py` — payload shape, LB→backend failover, all-fail raises
  - `test_api.py` — `/`, `/health`, `/search`, `/ask`, `/reset`, validation (TestClient)
  - `conftest.py` fixtures: isolated Chroma store, populated store, mocked LLM
- `requirements-dev.txt`, `pytest.ini`.

### Changed
- **Loading UX**: replaced the single static "Searching the docs…" (misleading —
  most of the wait is generation) with an animated, phased indicator:
  *Searching the documentation → Reading the sources → Writing a grounded answer*,
  with blinking dots. Cleared on response/error.
- Removed the old `test_smoke.py` (superseded by the suite).

### How to run
    source .venv/bin/activate
    pip install -r requirements-dev.txt
    python -m pytest

## [0.4.0] — 2026-07-20 — Conversational memory (with strict grounding)

### Added
- **Multi-turn conversation memory** so follow-ups work ("why is that needed?",
  "how do I fix it?"):
  - `app/memory.py` — per-session, in-process history (last `HISTORY_TURNS`, default 6).
  - `app/rag.py` — two-step turn: **condense** the follow-up into a standalone
    search query (resolving pronouns to the actual subject), then **answer**
    grounded, using the conversation only to understand intent.
  - `app/llm.py` — `chat_messages()` for full multi-turn message lists.
  - `app/api.py` — `/ask` accepts `session_id`; new `POST /reset` clears a session.
  - `chat.html` — generates a `session_id`, threads follow-ups, adds a **New chat** button.
- `config.py` — `HISTORY_TURNS` setting.
- `docs/06-conversation-memory.md` — how memory + grounding coexist.

### Changed
- Answer post-processing (`app/rag.py`): strip the model's own "Sources:" line
  (the API returns accurate sources from metadata) and, on a refusal, return no
  sources/passages. Fixes the "Sources: <5>" artifact and sources-on-refusal.
- Hardened `CONDENSE_SYSTEM` with an explicit pronoun→subject rule + example,
  after a live test showed "that one" drifting to an unrelated chunk.

### Verified (live + in the browser UI)
- Follow-ups resolve correctly across 3 turns; "it"/"that one" map to the right
  subject.
- Strict grounding still holds mid-conversation: "Does it integrate with
  Salesforce?" → "I don't have that in the documentation."
- Chat UI end-to-end: bubbles, filename source chips, expandable passages, New chat.

## [0.3.0] — 2026-07-20 — Chat UI

### Added
- **Chat UI** served by the existing FastAPI app at `http://127.0.0.1:8000/`
  (`app/static/chat.html`, served via a new `GET /` route). Single self-contained
  page, no new dependencies, no extra server.
- Features: question box (Enter to send, Shift+Enter newline), user/assistant
  bubbles, source-file chips under each answer, an expandable "retrieved passages"
  panel (with similarity scores) for verification, and a live index/model status
  badge in the header (reads `/health`).

### Verified
- `GET /` serves the page; `POST /ask` returns grounded answers with sources.

## [0.2.1] — 2026-07-20 — Remove client-specific (WBA) data from the index

### Changed
- **Excluded all WBA (client-specific) docs** from the knowledge base. The index
  now holds only generic, product-level CBX documentation. Rebuilt the index:
  **236 chunks** (was 270 — 34 WBA chunks removed).
- `docs/05-cbx-data.md`: WBA moved to an explicit "Excluded — client-specific
  (do NOT ingest)" section; ingestion commands now list each generic file
  explicitly instead of pointing at a whole folder, so no client doc can land in
  the general index by accident.

### Rationale
- Client-confidential, single-implementation material (approval templates, D&B
  routing, environment configs, customer names) does not belong in a general CBX
  assistant and could leak client detail into unrelated answers. A per-client
  assistant, if ever needed, should be a separate isolated index.

### Verified
- Generic questions still answer correctly (codelist shape, OpenSearch "No records
  found").
- WBA content no longer appears in retrieval results.

## [0.2.0] — 2026-07-20 — Real CBX corpus ingested & validated

### Added
- Ingested the full CBX documentation corpus — **270 chunks** total:
  - `TRADEBEYOND_KNOWLEDGE_BASE.md` (83), `CBX_API_HANDOUT.md` (20)
  - WBA As-Is workflow docs, incl. detailed summary (34)
  - 7 TBY training PDFs — 12–14 May sessions (133)

### Changed
- **Hardened the grounded system prompt** (`app/rag.py`): the model must always
  write the answer body first and may never return a "Sources:"-only reply. Fixed
  a reproducible case where qwen2.5:7b emitted only a sources line for the
  "No records found / OpenSearch" question.

### Verified (live, against the real CBX corpus)
- "What causes a 500 when importing colors?" → correct: codelist field sent as a
  plain string instead of `{code, name, version}`.
- "Correct shape for a codelist field?" → correct: `{code, name, version}`.
- "What must be configured before creating an item?" → correct: Code Lists first.
- "Why does a list show 'No records found'?" → correct: missing OpenSearch index
  (`index_not_found_exception`), a backend infra issue, fix = provision the index.
- "How is supplier approval routed by D&B risk?" → correct: Low = auto-approve,
  Medium/High = manual Sourcing Approver review.
- Guardrail intact: out-of-scope ("vacation policy?") → "I don't have that in the
  documentation."

### Known minor item (Phase 2)
- The in-answer "Sources:" line sometimes shows the passage number (e.g. `<1>`)
  instead of the filename. Cosmetic only — the JSON `sources` field returned by
  the API is always accurate (derived from chunk metadata, not the LLM text).

## [0.1.1] — 2026-07-20 — Python 3.9 fix + full end-to-end verification

### Fixed
- **Python 3.9 compatibility**: Pydantic models in `app/api.py` used `int | None`
  union syntax, which Pydantic evaluates at runtime and 3.9 cannot parse. Switched
  to `Optional[int]`. (Function-signature unions elsewhere are fine — deferred by
  `from __future__ import annotations` and never runtime-evaluated.)

### Changed
- **Refined the grounded system prompt** (`app/rag.py`) so the model cites sources
  ONLY when it actually answers; an out-of-scope question now returns exactly
  "I don't have that in the documentation." with no trailing sources line.

### Verified (end to end, live)
- Load balancer up; backend health check green (`/lb/health`).
- RAG API healthy; 3 sample chunks indexed.
- Full `/ask` path works on **llama3.2** and on **qwen2.5:7b**:
  - "Why do I get a 401?" → correct, grounded, cited.
  - "Onboarding order?" → correct 4-step order, grounded, cited.
  - "500 creating a widget?" → correct cause (size as string), cited.
- **Anti-hallucination guardrail confirmed**: out-of-scope question →
  "I don't have that in the documentation." (no sources).
- `qwen2.5:7b` pulled and set as default LLM.


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
