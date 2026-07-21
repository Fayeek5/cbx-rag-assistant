"""Freshservice connector — resolved/closed tickets via the tickets API."""
from __future__ import annotations

from config import settings
from app.connectors.base import TicketConnector

# Freshservice status codes: 2=Open, 3=Pending, 4=Resolved, 5=Closed
_RESOLVED = {4, 5}
_STATUS_NAME = {2: "Open", 3: "Pending", 4: "Resolved", 5: "Closed"}


class FreshserviceConnector(TicketConnector):
    name = "freshservice"

    def check_config(self):
        if not (settings.freshservice_domain and settings.freshservice_api_key):
            return ("Set freshservice_domain in .env and FRESHSERVICE_API_KEY "
                    "(freshservice_api_key) as a secret in .env.")
        return None

    @staticmethod
    def normalize(tickets: list[dict]) -> list[dict]:
        out = []
        for t in tickets:
            if t.get("status") not in _RESOLVED:
                continue
            out.append({
                "id": str(t.get("id", "")),
                "summary": t.get("subject", "") or "",
                "description": t.get("description_text") or t.get("description", "") or "",
                "resolution": "",  # in conversations/notes; see docs
                "component": t.get("category", "") or "",
                "status": _STATUS_NAME.get(t.get("status"), str(t.get("status", ""))),
            })
        return out

    def fetch(self, limit=None):
        base = f"https://{settings.freshservice_domain}".rstrip("/")
        auth = (settings.freshservice_api_key, "X")  # api key as basic-auth username
        results: list[dict] = []
        page = 1
        with self._client() as client:
            while True:
                r = client.get(f"{base}/api/v2/tickets",
                               params={"page": page, "per_page": 100}, auth=auth)
                r.raise_for_status()
                tickets = r.json().get("tickets", [])
                results.extend(self.normalize(tickets))
                if not tickets or (limit and len(results) >= limit):
                    break
                page += 1
        return results[:limit] if limit else results
