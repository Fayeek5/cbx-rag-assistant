"""Scan the indexed corpus (or a file/dir) for PII before it goes to users.

Usage:
    python scripts/scan_pii.py              # scans the current vector store
    python scripts/scan_pii.py <path>       # scans a file or directory instead

Reports any emails, phone numbers, card-like numbers, SSNs, or API tokens found,
grouped by source, so you can scrub client data out of the knowledge base.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.security import find_pii                       # noqa: E402


def _scan_store():
    from app import vectorstore
    ids, docs, metas = vectorstore.all_chunks()
    return [((m or {}).get("source", "?"), d) for m, d in zip(metas, docs)]


def _scan_path(path: str):
    from app.ingest import iter_supported_files, load_file
    files = [path] if os.path.isfile(path) else list(iter_supported_files(path))
    return [(f, load_file(f)) for f in files]


def main():
    items = _scan_path(sys.argv[1]) if len(sys.argv) > 1 else _scan_store()
    total = 0
    by_source: dict[str, list] = {}
    for source, text in items:
        hits = find_pii(text)
        if hits:
            by_source.setdefault(source.split("/")[-1], [])
            for h in hits:
                by_source[source.split("/")[-1]].append(h)
                total += 1

    if not total:
        print("No PII patterns found. ✅")
        return
    print(f"Found {total} potential PII span(s):\n")
    for src, hits in by_source.items():
        print(f"  {src}  ({len(hits)})")
        seen = set()
        for h in hits:
            key = (h["type"], h["match"])
            if key in seen:
                continue
            seen.add(key)
            print(f"    [{h['type']}] {h['match']}")
    print("\nReview these — scrub client/personal data before indexing for users.")


if __name__ == "__main__":
    main()
