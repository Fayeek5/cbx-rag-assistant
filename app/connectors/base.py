"""Common connector interface."""
from __future__ import annotations

import httpx

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


class TicketConnector:
    name = "base"

    def check_config(self) -> str | None:
        """Return an error string if required config/secrets are missing, else None."""
        return "not implemented"

    def fetch(self, limit: int | None = None) -> list[dict]:
        """Fetch resolved tickets and return normalized dicts."""
        raise NotImplementedError

    @staticmethod
    def _client() -> httpx.Client:
        return httpx.Client(timeout=_TIMEOUT)
