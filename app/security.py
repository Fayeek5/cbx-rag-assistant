"""PII detection / redaction + simple input guards.

Used to (a) redact sensitive values before they are written to logs, and
(b) scan the document corpus for PII that shouldn't be indexed. Detection is
regex-based — good for the common, high-risk patterns; not a substitute for a
full DLP tool, but the right first line of defence for a local assistant.
"""
from __future__ import annotations

import re

# Each pattern maps to the label used in its redaction placeholder.
_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("CARD", re.compile(r"\b(?:\d[ -]*?){13,16}\b")),                 # credit-card-like
    ("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),                    # US SSN
    ("AWS_KEY", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("TOKEN", re.compile(r"\b(?:sk|pk|ghp|xox[baprs])[-_][A-Za-z0-9]{16,}\b")),
    ("BEARER", re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._\-]{16,}")),
    ("PHONE", re.compile(r"(?<!\d)(?:\+?\d{1,3}[ -]?)?(?:\(?\d{3}\)?[ -]?)\d{3}[ -]?\d{4}(?!\d)")),
]


def find_pii(text: str) -> list[dict]:
    """Return a list of {type, match} for every PII-like span found."""
    hits: list[dict] = []
    for label, pat in _PATTERNS:
        for m in pat.finditer(text or ""):
            hits.append({"type": label, "match": m.group(0)})
    return hits


def redact(text: str) -> str:
    """Replace PII-like spans with [REDACTED_<TYPE>] placeholders."""
    if not text:
        return text
    out = text
    for label, pat in _PATTERNS:
        out = pat.sub(f"[REDACTED_{label}]", out)
    return out


def has_pii(text: str) -> bool:
    return bool(find_pii(text))
