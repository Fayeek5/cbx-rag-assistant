"""RAG orchestration with conversational memory and strict doc grounding.

Two-step design so the assistant can chat naturally while its FACTS stay locked
to the documentation:

  1. CONDENSE — if there's prior conversation, rewrite the (possibly elliptical)
     follow-up into a standalone search query. This uses the conversation only to
     resolve references like "the second one" — it does not answer anything.
  2. ANSWER — retrieve docs for that standalone query, then generate an answer
     that may use the conversation ONLY to understand intent, but must draw every
     fact from the retrieved passages. If the passages don't contain the answer,
     it says "I don't have that in the documentation." — even for follow-ups.
"""
from __future__ import annotations

import re

from app import vectorstore, memory
from app.llm import chat, chat_messages

REFUSAL = "I don't have that in the documentation."


def _clean_answer(text: str) -> str:
    """Strip the model's own trailing 'Sources:' line — the API returns accurate
    sources separately (from chunk metadata) and the UI renders them as chips."""
    return re.sub(r"\n*\s*Sources?:.*$", "", text.strip(), flags=re.IGNORECASE | re.DOTALL).strip()

# ── Step 1: condense a follow-up into a standalone query ─────────────────
CONDENSE_SYSTEM = (
    "You rewrite the user's latest message into a STANDALONE documentation search "
    "query.\n"
    "- Replace every pronoun or vague reference (it, that, that one, this, the "
    "second one, the error) with the SPECIFIC subject it refers to, taken from the "
    "conversation. The rewritten query must name that subject explicitly.\n"
    "- Preserve the user's actual intent; do NOT answer, do NOT add new facts.\n"
    "- If already standalone, return it unchanged.\n"
    "- Output ONLY the rewritten query.\n\n"
    "Example:\n"
    "  assistant (earlier): 'Code Lists must be configured before creating an item.'\n"
    "  user (latest): 'why is that one needed?'\n"
    "  rewritten: 'Why must Code Lists be configured before creating an item?'"
)


def _condense(history: list[dict], question: str) -> str:
    if not history:
        return question
    convo = "\n".join(f"{m['role']}: {m['content']}" for m in history)
    user = f"Conversation so far:\n{convo}\n\nLatest user message: {question}\n\nStandalone search query:"
    try:
        q = chat(CONDENSE_SYSTEM, user).strip()
        # guard against the model returning something empty/huge
        return q if 0 < len(q) <= 400 else question
    except Exception:  # noqa: BLE001 - if condensing fails, fall back to raw question
        return question


# ── Step 2: answer, strictly grounded ────────────────────────────────────
ANSWER_SYSTEM = (
    "You are a documentation assistant for the CBX / TradeBeyond platform, in an "
    "ongoing conversation with the user.\n\n"
    "STRICT GROUNDING RULES (highest priority):\n"
    "1. Every fact in your answer MUST come from the numbered CONTEXT passages "
    "given with the current question. \n"
    "2. Use the earlier conversation ONLY to understand what the user is referring "
    "to — NEVER as a source of facts, and never carry over a fact that isn't in "
    "the current CONTEXT.\n"
    "3. Do NOT use outside or general knowledge. Do NOT guess or infer beyond the "
    "passages.\n"
    "4. If the CONTEXT does not contain the answer, reply with EXACTLY this and "
    "nothing else: I don't have that in the documentation.\n\n"
    "When you can answer: FIRST write the answer in 1-5 sentences, technical and "
    "concise. THEN on a new line: Sources: <file1>, <file2> (only files you used). "
    "Never reply with only a 'Sources:' line."
)


def _format_context(passages: list[dict]) -> str:
    return "\n\n".join(
        f"[{i}] (source: {p['source']})\n{p['text']}" for i, p in enumerate(passages, 1)
    )


def answer(question: str, session_id: str = "", top_k: int | None = None) -> dict:
    """One conversational turn. Retrieves for the resolved query, answers grounded,
    and records the turn in session memory. Returns answer + sources + passages."""
    history = memory.get_history(session_id)

    # 1. resolve follow-ups into a standalone query for retrieval
    search_query = _condense(history, question)

    # 2. retrieve
    passages = vectorstore.query(search_query, top_k=top_k)
    if not passages:
        ans = "I don't have that in the documentation."
        memory.append(session_id, "user", question)
        memory.append(session_id, "assistant", ans)
        return {"answer": ans, "sources": [], "passages": [], "search_query": search_query}

    # 3. build the multi-turn message list:
    #    system + prior turns (for intent) + current user turn (with CONTEXT)
    messages: list[dict] = [{"role": "system", "content": ANSWER_SYSTEM}]
    messages.extend(history)  # prior user/assistant turns, verbatim
    context = _format_context(passages)
    messages.append({
        "role": "user",
        "content": f"CONTEXT passages:\n\n{context}\n\n---\nQuestion: {question}",
    })

    text = _clean_answer(chat_messages(messages))

    # if the model refused, don't show sources/passages (nothing was actually used)
    refused = REFUSAL.rstrip(".").lower() in text.lower()
    if refused:
        text = REFUSAL
        sources: list[str] = []
        shown_passages: list[dict] = []
    else:
        sources = sorted({p["source"] for p in passages})
        shown_passages = passages

    # 4. record the turn (store the raw question + the cleaned answer)
    memory.append(session_id, "user", question)
    memory.append(session_id, "assistant", text)

    return {"answer": text, "sources": sources, "passages": shown_passages, "search_query": search_query}
