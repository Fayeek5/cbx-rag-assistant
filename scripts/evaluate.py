"""Run the evaluation set against the live pipeline (needs Ollama running).

Usage:
    python scripts/evaluate.py                 # uses eval/cases.json
    python scripts/evaluate.py my_cases.json

Exercises the REAL retriever + RAG (LLM) for each case, scores it, prints a
table + summary, and writes data/eval_results.json. Use it before/after changes
to catch regressions in retrieval, grounding, or answer quality.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.rag import answer            # noqa: E402
from app.evaluate import score_case, summarize  # noqa: E402


def main():
    cases_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "eval", "cases.json")
    with open(cases_path, encoding="utf-8") as f:
        cases = json.load(f)

    scored = []
    for i, case in enumerate(cases, 1):
        # fresh session per case so history never leaks between cases
        result = answer(case["question"], session_id=f"eval-{i}")
        s = score_case(case, result)
        scored.append(s)
        mark = "PASS" if s["passed"] else "FAIL"
        detail = []
        if s["refusal_ok"] is False: detail.append(f"refusal(got refused={s['refused']}, expected={s['expected_refuse']})")
        if s["retrieval_ok"] is False: detail.append("retrieval(expected source missing)")
        if s["answer_ok"] is False: detail.append(f"answer(missing {s['missing_keywords']})")
        print(f"[{mark}] {case['question'][:60]}" + (("  <- " + "; ".join(detail)) if detail else ""))

    summary = summarize(scored)
    print("\n" + "=" * 50)
    print(f"Passed {summary['passed']}/{summary['total']}  (pass rate {summary['pass_rate']})")
    print(f"  refusal accuracy   : {summary['refusal_accuracy']}")
    print(f"  retrieval recall   : {summary['retrieval_recall']}")
    print(f"  answer keyword rate: {summary['answer_keyword_rate']}")

    os.makedirs("data", exist_ok=True)
    with open(os.path.join("data", "eval_results.json"), "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "cases": scored}, f, indent=2)
    print("\nWrote data/eval_results.json")

    sys.exit(0 if summary["failed"] == 0 else 1)


if __name__ == "__main__":
    main()
