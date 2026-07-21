# 07 — Support Tickets & Agent-Assist

Resolved tickets are the highest-value corpus for support: they capture how CBX
actually breaks and gets fixed — knowledge that isn't in the product docs. This
module ingests them and adds an **agent-assist** endpoint that drafts a grounded
triage for a support engineer to review.

## How it fits

- Tickets are ingested into the **same vector store** as the docs, tagged with a
  `ticket:<id>` source. So retrieval draws on past tickets *and* documentation
  together.
- `POST /assist {ticket}` retrieves the most similar resolved tickets + doc
  passages and drafts: **probable cause → suggested reply → confidence** (with a
  Low-confidence → escalate signal). It always drafts (no hard refusal) because a
  human reviews it — but it stays grounded in the retrieved context.

## Ingesting tickets

```bash
source .venv/bin/activate
python scripts/ingest_tickets.py samples/sample_tickets.jsonl
```

Try it:

```bash
curl -s http://127.0.0.1:8000/assist -H 'content-type: application/json' \
  -d '{"ticket":"Customer says color import returns a 500 error with no detail"}' \
  | python3 -m json.tool
```

## Ticket file format

JSONL (one object per line), a JSON array, or CSV. Fields (only `id` or
`summary` strictly required, but resolution is what makes it useful):

| field | meaning |
|---|---|
| `id` / `key` | ticket identifier (e.g. CBX-1012) |
| `summary` | short title |
| `description` | the reported problem |
| `resolution` | **how it was fixed** — the most valuable field |
| `component` | area (API, Search, Workflow…) |
| `status` | e.g. Resolved |

## Exporting real Jira tickets

1. In Jira, filter to **Resolved/Closed** issues for the CBX project.
2. Export to CSV (Issues → Export → CSV) or use the Jira REST API.
3. Map columns to the fields above — at minimum `id`, `summary`, `description`,
   and the resolution/comment that records the fix.
4. `python scripts/ingest_tickets.py your_export.csv`

Then re-run `scripts/evaluate.py` with ticket-based cases to measure how much the
past tickets improve support answers.

## Rollout note (from the RAG PDF's plan)

Start with **agent-assist** (engineer reviews every draft) before anything
customer-facing. The `/assist` draft + cited sources let an engineer verify in
seconds; measure deflection and time-to-resolution before considering a
customer-facing bot.
