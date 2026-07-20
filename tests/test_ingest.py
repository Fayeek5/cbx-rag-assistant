"""Document loading + chunking."""
from __future__ import annotations

import os

from app.ingest import Chunk, chunk_text, load_and_chunk, iter_supported_files


def test_chunk_text_produces_indexed_chunks():
    text = "\n\n".join(f"Paragraph {i} with enough words to matter here." for i in range(40))
    chunks = chunk_text(text, source="mem.md")
    assert len(chunks) > 1
    assert all(isinstance(c, Chunk) for c in chunks)
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
    assert all(c.source == "mem.md" for c in chunks)


def test_chunk_respects_size_roughly(monkeypatch):
    from config import settings
    monkeypatch.setattr(settings, "chunk_size", 200)
    monkeypatch.setattr(settings, "chunk_overlap", 40)
    text = "\n\n".join(["word " * 50 for _ in range(10)])
    chunks = chunk_text(text, source="s")
    # no chunk should vastly exceed the configured size
    assert max(len(c.text) for c in chunks) <= 200 + 60


def test_empty_text_yields_no_chunks():
    assert chunk_text("   \n\n  ", source="s") == []


def test_section_heading_prefixed_on_chunks():
    text = "## Colors\n\nColors have HEX and RGB values.\n\n## Vendors\n\nVendors are suppliers."
    chunks = chunk_text(text, source="kb.md")
    # each chunk should carry its section heading for context
    assert any(c.text.startswith("## Colors") for c in chunks)
    assert any(c.text.startswith("## Vendors") for c in chunks)


def test_table_kept_together(monkeypatch):
    from config import settings
    monkeypatch.setattr(settings, "chunk_size", 2000)
    table = "| a | b |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |"
    text = f"## API\n\nIntro line.\n\n{table}"
    chunks = chunk_text(text, source="api.md")
    # the whole table should live in one chunk, not split across rows
    joined = [c.text for c in chunks if "| 1 | 2 |" in c.text]
    assert joined and "| 3 | 4 |" in joined[0]


def test_load_and_chunk_markdown(tmp_path):
    p = tmp_path / "doc.md"
    p.write_text("# Title\n\nFirst para.\n\nSecond para.", encoding="utf-8")
    chunks = load_and_chunk(str(p))
    assert chunks and "First para" in " ".join(c.text for c in chunks)


def test_iter_supported_files(tmp_path):
    (tmp_path / "a.md").write_text("x", encoding="utf-8")
    (tmp_path / "b.txt").write_text("y", encoding="utf-8")
    (tmp_path / "c.png").write_text("z", encoding="utf-8")  # unsupported
    found = {os.path.basename(f) for f in iter_supported_files(str(tmp_path))}
    assert found == {"a.md", "b.txt"}
