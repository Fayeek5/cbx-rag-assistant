"""RAG orchestration: answer cleaning, refusal handling, grounding, memory wiring.

LLM is mocked (mock_llm fixture); retrieval is real against a populated store.
"""
from __future__ import annotations

from app import rag, memory


def test_clean_answer_strips_sources_line():
    assert rag._clean_answer("The answer.\nSources: a.md, b.md") == "The answer."
    assert rag._clean_answer("Answer only") == "Answer only"


def test_answer_returns_sources_and_passages(populated_store, mock_llm):
    mock_llm["reply"] = "Codelist fields are {code, name, version}.\nSources: api.md"
    out = rag.answer("what shape is a codelist field?", session_id="t1")
    assert out["answer"] == "Codelist fields are {code, name, version}."  # sources line stripped
    assert out["sources"]           # populated from chunk metadata
    assert out["passages"]          # retrieved passages returned


def test_refusal_blanks_sources(populated_store, mock_llm):
    mock_llm["reply"] = "I don't have that in the documentation."
    out = rag.answer("what is the capital of France?", session_id="t2")
    assert out["answer"] == "I don't have that in the documentation."
    assert out["sources"] == []
    assert out["passages"] == []


def test_answer_records_turn_in_memory(populated_store, mock_llm):
    sid = "t3"
    memory.reset(sid)
    rag.answer("what shape is a codelist field?", session_id=sid)
    hist = memory.get_history(sid)
    assert [m["role"] for m in hist] == ["user", "assistant"]


def test_condense_returns_question_when_no_history(populated_store, mock_llm):
    # with no history, the raw question is used as the search query
    out = rag.answer("what is a codelist field?", session_id="fresh-session")
    assert out["search_query"] == "what is a codelist field?"


def test_condense_uses_llm_on_followup(populated_store, mock_llm):
    sid = "t4"
    memory.reset(sid)
    rag.answer("what must be configured first?", session_id=sid)
    # mock condenser returns holder reply; set it to a standalone rewrite
    mock_llm["reply"] = "Why must Code Lists be configured before creating an item?"
    out = rag.answer("why is that needed?", session_id=sid)
    assert out["search_query"] == "Why must Code Lists be configured before creating an item?"
