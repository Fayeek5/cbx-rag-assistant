"""Ingest a directory (or single file) of documents into the vector store.

Usage:
    python scripts/ingest_docs.py <path> [--reset]

    <path>    A file or directory. Supported: .md .txt .pdf .docx
    --reset   Drop the existing collection before ingesting (clean rebuild)

Examples:
    python scripts/ingest_docs.py sample_docs/            # test corpus first
    python scripts/ingest_docs.py ../cbx-playwright/ --reset   # real CBX docs
"""
from __future__ import annotations

import argparse
import os
import sys

# make the project root importable when run as a script
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import vectorstore                      # noqa: E402
from app.ingest import iter_supported_files, load_and_chunk  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="Ingest docs into the RAG vector store.")
    ap.add_argument("path", help="File or directory to ingest")
    ap.add_argument("--reset", action="store_true", help="Wipe collection first")
    args = ap.parse_args()

    if args.reset:
        print("Resetting collection...")
        vectorstore.reset()

    files = [args.path] if os.path.isfile(args.path) else list(iter_supported_files(args.path))
    if not files:
        print(f"No supported files found under: {args.path}")
        return

    total_chunks = 0
    for i, path in enumerate(files, 1):
        try:
            chunks = load_and_chunk(path)
            added = vectorstore.add_chunks(chunks)
            total_chunks += added
            print(f"[{i}/{len(files)}] {path} -> {added} chunks")
        except Exception as e:  # noqa: BLE001
            print(f"[{i}/{len(files)}] {path} -> SKIPPED ({e})")

    print(f"\nDone. {total_chunks} chunks now indexed (collection total: {vectorstore.count()}).")


if __name__ == "__main__":
    main()
