"""Generic REST connector — any 3rd-party source that returns JSON.

Configure via .env:
  generic_url            full URL returning JSON
  generic_auth_header    optional, e.g. "Bearer xyz" (secret)
  generic_results_path   dot-path to the array of tickets, e.g. "data.tickets"
  generic_field_map      JSON mapping OUR fields -> source keys, e.g.
                         {"id":"key","summary":"title","description":"body",
                          "resolution":"fix","component":"area","status":"state"}
"""
from __future__ import annotations

import json

from config import settings
from app.connectors.base import TicketConnector

_OUR_FIELDS = ["id", "summary", "description", "resolution", "component", "status"]


def _dig(obj, path: str):
    cur = obj
    for part in [p for p in path.split(".") if p]:
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


class GenericConnector(TicketConnector):
    name = "generic"

    def check_config(self):
        if not settings.generic_url:
            return "Set generic_url (and optionally generic_field_map/results_path/auth_header) in .env."
        return None

    @staticmethod
    def normalize(payload, results_path: str = "", field_map_json: str = "") -> list[dict]:
        rows = _dig(payload, results_path) if results_path else payload
        if isinstance(rows, dict):
            rows = [rows]
        if not isinstance(rows, list):
            return []
        fmap = json.loads(field_map_json) if field_map_json else {}
        out = []
        for row in rows:
            rec = {}
            for our in _OUR_FIELDS:
                src_key = fmap.get(our, our)  # default: identity mapping
                val = _dig(row, src_key) if "." in src_key else (row.get(src_key) if isinstance(row, dict) else None)
                rec[our] = "" if val is None else (val if isinstance(val, str) else str(val))
            if rec.get("id") or rec.get("summary"):
                out.append(rec)
        return out

    def fetch(self, limit=None):
        headers = {"Accept": "application/json"}
        if settings.generic_auth_header:
            headers["Authorization"] = settings.generic_auth_header
        with self._client() as client:
            r = client.get(settings.generic_url, headers=headers)
            r.raise_for_status()
            rows = self.normalize(r.json(), settings.generic_results_path, settings.generic_field_map)
        return rows[:limit] if limit else rows
