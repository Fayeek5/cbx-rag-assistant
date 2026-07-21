"""Jira Cloud connector — resolved issues via the REST search API."""
from __future__ import annotations

import httpx

from config import settings
from app.connectors.base import TicketConnector

_FIELDS = "summary,description,resolution,components,status"


def _adf_text(node) -> str:
    """Flatten Atlassian Document Format (rich-text description) to plain text."""
    if isinstance(node, str):
        return node
    if isinstance(node, dict):
        if node.get("type") == "text":
            return node.get("text", "")
        return "".join(_adf_text(c) for c in node.get("content", []))
    if isinstance(node, list):
        return "".join(_adf_text(c) for c in node)
    return ""


class JiraConnector(TicketConnector):
    name = "jira"

    def check_config(self):
        if not (settings.jira_base_url and settings.jira_email and settings.jira_api_token):
            return ("Set jira_base_url, jira_email in .env and JIRA_API_TOKEN "
                    "(jira_api_token) as a secret in .env.")
        return None

    @staticmethod
    def normalize(issues: list[dict]) -> list[dict]:
        out = []
        for it in issues:
            f = it.get("fields", {}) or {}
            res = f.get("resolution") or {}
            comps = f.get("components") or []
            out.append({
                "id": it.get("key"),
                "summary": f.get("summary", "") or "",
                "description": _adf_text(f.get("description")) or "",
                "resolution": (res.get("name", "") if isinstance(res, dict) else str(res or "")),
                "component": (comps[0].get("name", "") if comps else ""),
                "status": (f.get("status") or {}).get("name", ""),
            })
        return out

    def fetch(self, limit=None):
        base = settings.jira_base_url.rstrip("/")
        auth = (settings.jira_email, settings.jira_api_token)
        results: list[dict] = []
        start = 0
        with self._client() as client:
            while True:
                page = min(100, (limit - len(results)) if limit else 100)
                r = client.get(f"{base}/rest/api/3/search",
                               params={"jql": settings.jira_jql, "fields": _FIELDS,
                                       "startAt": start, "maxResults": page},
                               auth=auth, headers={"Accept": "application/json"})
                r.raise_for_status()
                data = r.json()
                issues = data.get("issues", [])
                results.extend(self.normalize(issues))
                start += len(issues)
                if not issues or start >= data.get("total", 0) or (limit and len(results) >= limit):
                    break
        return results[:limit] if limit else results
