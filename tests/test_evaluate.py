"""Eval scoring logic (pure, no LLM)."""
from __future__ import annotations

from app.evaluate import score_case, summarize


def test_answerable_pass():
    case = {"question": "q", "expect_contains": ["code", "version"],
            "expect_source": "api.md", "expect_refuse": False}
    result = {"answer": "Use {code, name, version} objects.",
              "sources": ["/x/api.md"], "passages": [{"source": "/x/api.md"}]}
    s = score_case(case, result)
    assert s["passed"] and s["refusal_ok"] and s["retrieval_ok"] and s["answer_ok"]


def test_answer_missing_keyword_fails():
    case = {"question": "q", "expect_contains": ["freight"], "expect_source": None, "expect_refuse": False}
    result = {"answer": "ELC is a cost concept.", "sources": [], "passages": []}
    s = score_case(case, result)
    assert not s["passed"] and s["answer_ok"] is False and s["missing_keywords"] == ["freight"]


def test_retrieval_miss_fails():
    case = {"question": "q", "expect_contains": [], "expect_source": "api.md", "expect_refuse": False}
    result = {"answer": "something", "sources": [], "passages": [{"source": "/x/other.md"}]}
    s = score_case(case, result)
    assert not s["passed"] and s["retrieval_ok"] is False


def test_refusal_expected_pass():
    case = {"question": "capital of France?", "expect_contains": [], "expect_source": None, "expect_refuse": True}
    result = {"answer": "I don't have that in the documentation.", "sources": [], "passages": []}
    s = score_case(case, result)
    assert s["passed"] and s["refusal_ok"]


def test_unexpected_refusal_fails():
    case = {"question": "real q", "expect_contains": [], "expect_source": None, "expect_refuse": False}
    result = {"answer": "I don't have that in the documentation.", "sources": [], "passages": []}
    s = score_case(case, result)
    assert not s["passed"] and s["refusal_ok"] is False


def test_summarize_rates():
    scored = [
        {"passed": True, "refusal_ok": True, "retrieval_ok": True, "answer_ok": True},
        {"passed": False, "refusal_ok": True, "retrieval_ok": False, "answer_ok": None},
    ]
    summ = summarize(scored)
    assert summ["total"] == 2 and summ["passed"] == 1
    assert summ["pass_rate"] == 0.5
    assert summ["refusal_accuracy"] == 1.0
    assert summ["retrieval_recall"] == 0.5
