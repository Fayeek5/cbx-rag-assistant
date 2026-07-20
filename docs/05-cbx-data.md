# 05 — Moving from Sample Docs to CBX Data

We deliberately test on tiny sample docs first (`sample_docs/`) to prove the
pipeline, then point ingestion at the real CBX corpus.

## The CBX corpus we already have

| Source file | What it adds to the RAG |
|---|---|
| `TRADEBEYOND_KNOWLEDGE_BASE.md` | Module concepts, prerequisites, onboarding sequence |
| `CBX_API_HANDOUT.md` | Field mappings, endpoint contracts, hard-won debug patterns |
| Training PDFs (12–14 May) | Official module explanations, quality process, ERP integration |
| WBA As-Is workflow docs | A real customer implementation (approval templates, D&B routing) |
| Import templates + migration notes | CSV→JSON mapping rules, codelist gotchas |
| **Resolved support tickets** (future) | How CBX actually breaks and gets fixed — the highest-value source for ticket handling |

## Ingesting CBX docs

```bash
source .venv/bin/activate

# start clean, then add each source
python scripts/ingest_docs.py ../cbx-playwright/TRADEBEYOND_KNOWLEDGE_BASE.md --reset
python scripts/ingest_docs.py ../cbx-playwright/CBX_API_HANDOUT.md
python scripts/ingest_docs.py ~/Downloads/WBA_As-Is_Workflow_Docs/
python scripts/ingest_docs.py ~/Downloads/   # picks up the training PDFs (.pdf supported)

# sanity check
curl -s http://127.0.0.1:8000/health | python3 -m json.tool   # indexed_chunks > 0
```

## Test questions to validate CBX retrieval quality

Use `/search` first (retrieval only), then `/ask`:

- "What must be configured before I can create an item?"
- "Why do I get a 500 error when importing colors?"
- "What does 'No records found' mean when data was imported?"
- "How is supplier approval routed based on D&B risk rating?"
- "What is the correct shape for a codelist field in the API?"

If `/search` returns the right passage but `/ask` doesn't use it well, the issue
is prompt/LLM. If `/search` misses, the issue is chunking/embedding — tune and
re-ingest.

## Improvements worth making for the CBX corpus specifically

1. **Section-aware chunking.** The knowledge base is heavily structured with
   Markdown headings. Splitting on `##`/`###` boundaries (instead of paragraphs)
   keeps each module's concept intact in one chunk. Change `chunk_text()` in
   `app/ingest.py`.
2. **Keep tables together.** The API handout has field-mapping tables; make sure
   a table isn't split across chunks (raise `CHUNK_SIZE`, or special-case `|`
   table rows).
3. **Metadata for filtering.** Tag chunks with module name / doc type so the API
   can filter (e.g. "only search the API handout"). Chroma supports metadata
   filters in `query()`.
4. **The Cantonese/English WBA doc** has mixed languages; bge-small is
   English-first. If retrieval on it is weak, switch to `bge-m3` (multilingual).
5. **Freshness.** Some docs are point-in-time (PREPROD configs change). Add a
   `timestamp`/`version` to chunk metadata (OKF-style) and prefer recent chunks.

## Open Knowledge Format (OKF) alignment

The Google OKF spec (markdown files + YAML frontmatter as a portable knowledge
bundle) fits this project well: our `.md` sources already are markdown, and
adding YAML frontmatter (`type`, `title`, `tags`, `timestamp`, `source`) would
let us carry structured metadata into chunk records for filtering and freshness.
Consider standardising the CBX corpus into an OKF bundle as it grows — it keeps
the knowledge portable and versionable alongside code.
