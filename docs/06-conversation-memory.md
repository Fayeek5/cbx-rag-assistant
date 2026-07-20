# 06 — Conversation Memory (with strict grounding)

The assistant holds a normal multi-turn conversation — you can ask a question,
then follow up with "why is that needed?" or "how do I fix it?" — while every
FACT it states stays locked to the indexed documentation.

## The two-step turn

Each turn runs two LLM steps so memory and grounding don't fight each other:

```
follow-up question + conversation history
        │
        ▼
1. CONDENSE  ── rewrite into a standalone search query
        │        e.g. "why is that one needed?"
        │        →  "Why must Code Lists be configured before creating an item?"
        │        (uses history ONLY to resolve references; adds no facts)
        ▼
2. RETRIEVE  ── vector search with the standalone query  (app/vectorstore.py)
        │
        ▼
3. ANSWER    ── system prompt + prior turns + retrieved CONTEXT
                 • conversation is used ONLY to understand intent
                 • every fact must come from the retrieved passages
                 • not in the passages → "I don't have that in the documentation."
```

Step 1 is why follow-ups work; step 3's system prompt (`ANSWER_SYSTEM` in
`app/rag.py`) is why grounding never leaks — the conversation can shape *what the
user means*, never *what is true*.

## Sessions

- Each browser conversation gets a `session_id` (generated client-side in
  `chat.html`, sent with every `/ask`).
- The server keeps the last `HISTORY_TURNS` (default 6) turns per session in
  memory (`app/memory.py`) — an in-process dict, not persisted. Restarting the
  server clears all conversations. For a persistent or multi-worker deployment,
  back `memory.py` with Redis or a database.
- **New chat** button → `POST /reset {session_id}` clears that conversation and
  starts a fresh `session_id`.

## Verified behaviour

| Turn | Input | Result |
|---|---|---|
| 1 | "What must be configured before creating an item?" | Code Lists & Lookup Lists |
| 2 | "Why is that one needed?" | resolves "that one" → Code Lists; explains why |
| 3 | "What happens if it is missing?" | resolves "it" → Code Lists; explains impact |
| — | "What causes a 500 importing colors?" → "How do I fix it?" | "it" → the 500 error; gives the fix |
| — | mid-chat: "Does it integrate with Salesforce?" | "I don't have that in the documentation." (grounding holds) |

## Tuning

- `HISTORY_TURNS` in `.env` — how many prior turns to remember (more = better
  context, longer prompts, slightly slower/cheaper trade-off).
- Follow-up resolution quality lives in `CONDENSE_SYSTEM` (`app/rag.py`); it
  explicitly replaces pronouns with the specific subject from the conversation.
