"""Connector normalization (pure — sample payloads, no live APIs)."""
from __future__ import annotations

from app.connectors import get_connector, REGISTRY
from app.connectors.jira import JiraConnector
from app.connectors.zendesk import ZendeskConnector
from app.connectors.freshservice import FreshserviceConnector
from app.connectors.generic import GenericConnector


def test_registry_has_all():
    assert set(REGISTRY) == {"jira", "zendesk", "freshservice", "generic"}
    assert get_connector("jira").name == "jira"


def test_jira_normalize_incl_adf_description():
    issues = [{
        "key": "CBX-1012",
        "fields": {
            "summary": "500 on color import",
            "description": {"type": "doc", "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "Import fails with 500."}]}]},
            "resolution": {"name": "Fixed"},
            "components": [{"name": "API"}],
            "status": {"name": "Done"},
        }}]
    out = JiraConnector.normalize(issues)
    assert out[0]["id"] == "CBX-1012"
    assert out[0]["description"] == "Import fails with 500."
    assert out[0]["component"] == "API" and out[0]["status"] == "Done"


def test_zendesk_normalize():
    results = [{"id": 42, "subject": "Login broken", "description": "cannot log in",
                "status": "solved", "result_type": "ticket", "via": {"channel": "web"}}]
    out = ZendeskConnector.normalize(results)
    assert out[0]["id"] == "42" and out[0]["summary"] == "Login broken"
    assert out[0]["component"] == "web"


def test_freshservice_normalize_filters_unresolved():
    tickets = [
        {"id": 1, "subject": "resolved one", "description_text": "x", "status": 4, "category": "API"},
        {"id": 2, "subject": "still open", "description_text": "y", "status": 2},
    ]
    out = FreshserviceConnector.normalize(tickets)
    assert len(out) == 1 and out[0]["id"] == "1" and out[0]["status"] == "Resolved"


def test_generic_normalize_with_field_map_and_path():
    payload = {"data": {"tickets": [
        {"key": "T-9", "title": "disk full", "body": "server out of space", "state": "closed"}]}}
    fmap = '{"id":"key","summary":"title","description":"body","status":"state"}'
    out = GenericConnector.normalize(payload, results_path="data.tickets", field_map_json=fmap)
    assert out[0]["id"] == "T-9" and out[0]["summary"] == "disk full"
    assert out[0]["status"] == "closed"


def test_connectors_report_missing_config():
    # with no .env creds set, each connector should report what's missing
    for name in REGISTRY:
        msg = get_connector(name).check_config()
        assert msg is None or isinstance(msg, str)
