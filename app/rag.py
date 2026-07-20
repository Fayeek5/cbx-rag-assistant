"""RAG orchestration: retrieve -> build grounded prompt -> generate.

The system prompt forces the model to answer ONLY from the retrieved context and
to say so when the answer isn't there. This is the core anti-hallucination
guardrail — critical for CBX support answers.
"""
from __future__ import annotations

from app import vectorstore
from app.llm import chat

SYSTEM_PROMPT = (
    "You are a documentation assistant for the CBX / TradeBeyond platform. "
    "Answer the user's question using ONLY the numbered context passages provided. "
    "If the answer IS contained in the context: answer concisely and technically, "
    "then on a new line cite the source file(s) you actually used as: "
    "Sources: <file1>, <file2>. "
    "If the answer is NOT contained in the context: reply with exactly this and "
    "nothing else: \"I don't have that in the documentation.\" (do not cite any sources)."
)


def _format_context(passages: list[dict]) -> str:
    blocks = []
    for i, p in enumerate(passages, 1):
        blocks.append(f"[{i}] (source: {p['source']})\n{p['text']}")
    return "\n\n".join(blocks)


def answer(question: str, top_k: int | None = None) -> dict:
    """Full RAG turn. Returns the answer plus the passages used (for auditing)."""
    passages = vectorstore.query(question, top_k=top_k)
    if not passages:
        return {"answer": "I don't have that in the documentation.", "sources": [], "passages": []}

    context = _format_context(passages)
    user_prompt = f"Context passages:\n\n{context}\n\n---\nQuestion: {question}"
    text = chat(SYSTEM_PROMPT, user_prompt)

    sources = sorted({p["source"] for p in passages})
    return {"answer": text, "sources": sources, "passages": passages}
