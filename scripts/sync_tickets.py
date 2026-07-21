"""Pull resolved tickets from an external system and ingest them.

Usage:
    python scripts/sync_tickets.py jira          # or zendesk | freshservice | generic
    python scripts/sync_tickets.py jira --limit 200
    python scripts/sync_tickets.py jira --dry-run   # fetch + print count, don't ingest

Credentials/config come from .env (see docs/07-tickets.md). Secrets never live
in code — set JIRA_API_TOKEN / ZENDESK_API_TOKEN / FRESHSERVICE_API_KEY etc. in
your local .env.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import vectorstore                              # noqa: E402
from app.connectors import get_connector, REGISTRY       # noqa: E402
from app.tickets import tickets_to_chunks                # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source", choices=list(REGISTRY))
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    conn = get_connector(args.source)
    err = conn.check_config()
    if err:
        print(f"Cannot sync '{args.source}': {err}")
        sys.exit(2)

    print(f"Fetching resolved tickets from {args.source}…")
    try:
        tickets = conn.fetch(limit=args.limit)
    except Exception as e:  # noqa: BLE001
        print(f"Fetch failed: {e}")
        sys.exit(1)
    print(f"Fetched {len(tickets)} ticket(s).")

    if args.dry_run:
        for t in tickets[:5]:
            print(f"  {t.get('id')}: {t.get('summary')[:70]}")
        print("(dry run — not ingested)")
        return

    added = vectorstore.add_chunks(tickets_to_chunks(tickets))
    print(f"Ingested {added}. Collection total: {vectorstore.count()}.")


if __name__ == "__main__":
    main()
