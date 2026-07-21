"""Support-ticket ingestion for agent-assist.

Resolved tickets are the highest-value corpus for support: they record how CBX
actually breaks and gets fixed. We turn each into a chunk (summary + problem +
resolution) tagged with a `ticket:<id>` source so it lives alongside the docs in
the same vector store and can be retrieved together.

Accepts JSONL, a JSON array, or CSV. Expected fields (all optional except id):
  id, summary, description, resolution, component, status
"""
from __future__ import annotations

import csv
import json
import os

from app.ingest import Chunk


def ticket_to_chunk(t: dict) -> Chunk:
    tid = str(t.get("id") or t.get("key") or "?")
    parts = [f"Ticket {tid}: {t.get('summary', '').strip()}"]
    if t.get("component"):
        parts.append(f"Component: {t['component']}")
    if t.get("description"):
        parts.append(f"Problem: {t['description'].strip()}")
    if t.get("resolution"):
        parts.append(f"Resolution: {t['resolution'].strip()}")
    return Chunk(text="\n\n".join(parts), source=f"ticket:{tid}", chunk_index=0)


def load_tickets(path: str) -> list[dict]:
    ext = os.path.splitext(path)[1].lower()
    with open(path, encoding="utf-8", errors="ignore") as f:
        if ext == ".csv":
            return list(csv.DictReader(f))
        if ext == ".jsonl":
            return [json.loads(line) for line in f if line.strip()]
        # .json — array or single object
        data = json.load(f)
        return data if isinstance(data, list) else [data]


def tickets_to_chunks(tickets: list[dict]) -> list[Chunk]:
    return [ticket_to_chunk(t) for t in tickets if (t.get("id") or t.get("key") or t.get("summary"))]
