"""PII detection + redaction."""
from __future__ import annotations

from app.security import find_pii, redact, has_pii


def test_detects_email():
    hits = find_pii("contact me at jane.doe@example.com please")
    assert any(h["type"] == "EMAIL" for h in hits)


def test_redacts_email_and_token():
    out = redact("email a@b.com token sk-ABCDEFGHIJKLMNOP1234")
    assert "a@b.com" not in out
    assert "[REDACTED_EMAIL]" in out
    assert "[REDACTED_TOKEN]" in out


def test_detects_ssn_and_card():
    assert has_pii("SSN 123-45-6789")
    assert has_pii("card 4111 1111 1111 1111")


def test_clean_text_untouched():
    txt = "Codelist fields must be {code, name, version} objects."
    assert redact(txt) == txt
    assert not has_pii(txt)


def test_bearer_token_redacted():
    out = redact("Authorization: Bearer abcdef0123456789ABCDEF")
    assert "[REDACTED_BEARER]" in out
