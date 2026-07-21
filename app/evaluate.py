"""Evaluation scoring logic (pure functions — no LLM/network, unit-testable).

A case is scored on three axes:
  - retrieval: did the expected source file appear in the retrieved passages?
  - refusal:   for should-refuse cases, did the assistant refuse (and not for others)?
  - answer:    does the answer contain all expected keywords (case-insensitive)?

The runner (scripts/evaluate.py) exercises the real pipeline and feeds results
here; these functions just decide pass/fail so they can be tested deterministically.
"""
from __future__ import annotations

REFUSAL = "I don't have that in the documentation."


def score_case(case: dict, result: dict) -> dict:
    """case: the eval spec; result: {answer, sources, passages}. Returns a scored dict."""
    answer = (result.get("answer") or "")
    sources = [s.split("/")[-1] for s in result.get("sources", [])]
    passages_sources = [(p.get("source") or "").split("/")[-1] for p in result.get("passages", [])]

    refused = REFUSAL.rstrip(".").lower() in answer.lower()
    expect_refuse = bool(case.get("expect_refuse"))

    # refusal axis
    refusal_ok = (refused == expect_refuse)

    # retrieval axis (only meaningful for answerable cases with an expected source)
    exp_src = case.get("expect_source")
    if expect_refuse or not exp_src:
        retrieval_ok = True
        retrieval_na = True
    else:
        retrieval_ok = exp_src in passages_sources or exp_src in sources
        retrieval_na = False

    # answer keyword axis (only for answerable cases)
    if expect_refuse:
        answer_ok = True
        answer_na = True
        missing = []
    else:
        kws = case.get("expect_contains", [])
        low = answer.lower()
        missing = [k for k in kws if k.lower() not in low]
        answer_ok = not missing
        answer_na = not kws

    passed = refusal_ok and retrieval_ok and answer_ok
    return {
        "question": case["question"],
        "passed": passed,
        "refusal_ok": refusal_ok,
        "retrieval_ok": retrieval_ok if not retrieval_na else None,
        "answer_ok": answer_ok if not answer_na else None,
        "refused": refused,
        "expected_refuse": expect_refuse,
        "missing_keywords": missing,
        "sources": sources,
    }


def summarize(scored: list[dict]) -> dict:
    total = len(scored)
    passed = sum(1 for s in scored if s["passed"])
    def rate(axis):
        vals = [s[axis] for s in scored if s.get(axis) is not None]
        return round(sum(vals) / len(vals), 3) if vals else None
    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": round(passed / total, 3) if total else 0.0,
        "refusal_accuracy": rate("refusal_ok"),
        "retrieval_recall": rate("retrieval_ok"),
        "answer_keyword_rate": rate("answer_ok"),
    }
