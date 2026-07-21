"""Ingest resolved support tickets into the vector store (for agent-assist).

Usage:
    python scripts/ingest_tickets.py samples/sample_tickets.jsonl

Tickets go into the SAME collection as the docs, tagged with a `ticket:<id>`
source, so agent-assist retrieves past tickets and documentation together.

To use real Jira tickets: export resolved issues to JSONL/CSV with columns
id, summary, description, resolution, component, status (see docs/07-tickets.md),
then point this script at the file.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import vectorstore                                  # noqa: E402
from app.tickets import load_tickets, tickets_to_chunks      # noqa: E402


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/ingest_tickets.py <tickets.jsonl|.json|.csv>")
        sys.exit(1)
    tickets = load_tickets(sys.argv[1])
    chunks = tickets_to_chunks(tickets)
    added = vectorstore.add_chunks(chunks)
    print(f"Ingested {added} ticket(s). Collection total: {vectorstore.count()}.")


if __name__ == "__main__":
    main()
