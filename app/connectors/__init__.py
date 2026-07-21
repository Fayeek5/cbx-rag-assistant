"""Ticket connectors — fetch resolved tickets from external systems and
normalize them to the standard schema (id, summary, description, resolution,
component, status) used by app.tickets.

Each connector splits HTTP (fetch) from parsing (normalize) so the normalization
is unit-testable with sample payloads and no live credentials.
"""
from __future__ import annotations

from app.connectors.base import TicketConnector
from app.connectors.jira import JiraConnector
from app.connectors.zendesk import ZendeskConnector
from app.connectors.freshservice import FreshserviceConnector
from app.connectors.generic import GenericConnector

REGISTRY: dict[str, type[TicketConnector]] = {
    "jira": JiraConnector,
    "zendesk": ZendeskConnector,
    "freshservice": FreshserviceConnector,
    "generic": GenericConnector,
}


def get_connector(name: str) -> TicketConnector:
    name = name.lower()
    if name not in REGISTRY:
        raise ValueError(f"Unknown connector '{name}'. Options: {', '.join(REGISTRY)}")
    return REGISTRY[name]()
