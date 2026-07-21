"""Zendesk connector — solved tickets via the Search API."""
from __future__ import annotations

from config import settings
from app.connectors.base import TicketConnector


class ZendeskConnector(TicketConnector):
    name = "zendesk"

    def check_config(self):
        if not (settings.zendesk_subdomain and settings.zendesk_email and settings.zendesk_api_token):
            return ("Set zendesk_subdomain, zendesk_email in .env and "
                    "ZENDESK_API_TOKEN (zendesk_api_token) as a secret in .env.")
        return None

    @staticmethod
    def normalize(results: list[dict]) -> list[dict]:
        out = []
        for t in results:
            if t.get("result_type") not in (None, "ticket"):
                continue
            out.append({
                "id": str(t.get("id", "")),
                "summary": t.get("subject", "") or "",
                "description": t.get("description", "") or "",
                "resolution": "",  # Zendesk keeps the fix in comments; see docs
                "component": (t.get("via", {}) or {}).get("channel", ""),
                "status": t.get("status", ""),
            })
        return out

    def fetch(self, limit=None):
        base = f"https://{settings.zendesk_subdomain}.zendesk.com"
        # Zendesk API-token auth: username is "{email}/token", password is the token
        auth = (f"{settings.zendesk_email}/token", settings.zendesk_api_token)
        url = f"{base}/api/v2/search.json"
        params = {"query": settings.zendesk_query}
        results: list[dict] = []
        with self._client() as client:
            while url:
                r = client.get(url, params=params, auth=auth)
                r.raise_for_status()
                data = r.json()
                results.extend(self.normalize(data.get("results", [])))
                url = data.get("next_page")
                params = None  # next_page is a full URL
                if limit and len(results) >= limit:
                    break
        return results[:limit] if limit else results
