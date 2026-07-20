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

from app import vectorstore, memory, retriever
from app.llm import chat, chat_messages

REFUSAL = "I don't have that in the documentation."

# ── Intent routing ───────────────────────────────────────────────────────
# The assistant should converse normally (greetings, "what can you do?") while
# gating FACTUAL answers to the docs. We classify each message first: only DOC
# questions go through retrieval + grounding.

CAPABILITY_TEXT = (
    "I'm the CBX / TradeBeyond documentation assistant. Ask me about the platform "
    "— how modules work, API field shapes, error causes, setup prerequisites — and "
    "I'll answer from the indexed documentation and cite the sources. If something "
    "isn't covered, I'll say \"I don't have that in the documentation.\""
)

# Fast, deterministic patterns for obvious cases (no LLM call needed).
_SMALLTALK_RE = re.compile(
    r"^\s*(hi|hii+|hey+|hello|hiya|yo|howdy|sup|good\s*(morning|afternoon|evening|day)|"
    r"thanks|thank\s*you|thankyou|ty|cheers|thx|"
    r"bye|goodbye|see\s*(you|ya)|take\s*care|"
    r"how\s*(are|r)\s*(you|u)|how'?s\s*it\s*going|what'?s\s*up)"
    r"[\s!.?]*$",
    re.IGNORECASE,
)
_META_RE = re.compile(
    r"(what\s*can\s*you\s*do|what\s*do\s*you\s*do|who\s*are\s*you|what\s*are\s*you|"
    r"what\s*can\s*i\s*ask|how\s*do\s*you\s*work|what\s*can\s*you\s*help|"
    r"^\s*help\s*$)",
    re.IGNORECASE,
)

INTENT_SYSTEM = (
    "Classify the user's latest message into exactly one label:\n"
    "SMALLTALK - greeting, farewell, thanks, or social pleasantry.\n"
    "META - a question about you (the assistant) or what you can do.\n"
    "DOC - any request for information, explanation, or help about the "
    "CBX/TradeBeyond product, INCLUDING short follow-ups (why, how, tell me more).\n"
    "When unsure, answer DOC. Output ONLY the label word."
)

SMALLTALK_SYSTEM = (
    "You are the CBX / TradeBeyond documentation assistant. The user sent a "
    "greeting or social message. Reply warmly in ONE short sentence and invite them "
    "to ask a documentation question. Do NOT state any facts about the product."
)


def _classify(history: list[dict], question: str) -> str:
    q = question.strip()
    if _SMALLTALK_RE.match(q):
        return "SMALLTALK"
    if _META_RE.search(q):
        return "META"
    # ambiguous → ask the LLM, defaulting to DOC (never skip grounding by mistake)
    try:
        label = chat(INTENT_SYSTEM, f"Latest user message: {q}\nLabel:").strip().upper()
        return label if label in {"SMALLTALK", "META", "DOC"} else "DOC"
    except Exception:  # noqa: BLE001
        return "DOC"


def _smalltalk_reply(history: list[dict], question: str) -> str:
    try:
        return chat(SMALLTALK_SYSTEM, question).strip() or \
            "Hi! Ask me anything about the CBX / TradeBeyond documentation."
    except Exception:  # noqa: BLE001
        return "Hi! Ask me anything about the CBX / TradeBeyond documentation."


def _record(session_id: str, question: str, answer_text: str) -> None:
    memory.append(session_id, "user", question)
    memory.append(session_id, "assistant", answer_text)


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
    """One conversational turn. Routes by intent: small-talk and capability
    questions get a conversational reply (no retrieval, no sources); documentation
    questions go through retrieval + strict grounding. Records the turn in memory."""
    history = memory.get_history(session_id)

    # 0. intent gate — only DOC questions touch the docs
    intent = _classify(history, question)
    if intent == "SMALLTALK":
        reply = _smalltalk_reply(history, question)
        _record(session_id, question, reply)
        return {"answer": reply, "sources": [], "passages": [], "intent": "smalltalk"}
    if intent == "META":
        _record(session_id, question, CAPABILITY_TEXT)
        return {"answer": CAPABILITY_TEXT, "sources": [], "passages": [], "intent": "meta"}

    # 1. resolve follow-ups into a standalone query for retrieval
    search_query = _condense(history, question)

    # 2. retrieve (hybrid + rerank) and apply the hard relevance gate
    passages = retriever.retrieve(search_query, top_k=top_k)
    if not retriever.passes_threshold(passages):
        _record(session_id, question, REFUSAL)
        return {"answer": REFUSAL, "sources": [], "passages": [],
                "search_query": search_query, "intent": "doc"}

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
    _record(session_id, question, text)

    return {"answer": text, "sources": sources, "passages": shown_passages,
            "search_query": search_query, "intent": "doc"}
