"""Document loading and chunking.

Supports .md, .txt, .pdf, .docx. Chunks by paragraph with a target size and
overlap, so a single chunk keeps related sentences together but neighbouring
chunks share context at their edges (helps retrieval recall).
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass

from config import settings


@dataclass
class Chunk:
    text: str
    source: str        # file path
    chunk_index: int   # position within the file


# ── Loaders ────────────────────────────────────────────────────────────
def _load_text(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def _load_pdf(path: str) -> str:
    from pypdf import PdfReader

    reader = PdfReader(path)
    return "\n\n".join((page.extract_text() or "") for page in reader.pages)


def _load_docx(path: str) -> str:
    import docx

    doc = docx.Document(path)
    return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())


_LOADERS = {
    ".md": _load_text,
    ".txt": _load_text,
    ".pdf": _load_pdf,
    ".docx": _load_docx,
}


def load_file(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    loader = _LOADERS.get(ext)
    if not loader:
        raise ValueError(f"Unsupported file type: {ext}")
    return loader(path)


# ── Chunking ───────────────────────────────────────────────────────────
_HEADING_RE = re.compile(r"^#{1,6}\s+\S")


def _is_table_line(line: str) -> bool:
    return line.lstrip().startswith("|")


def _split_blocks(text: str) -> list[str]:
    """Split into blocks on blank lines, but keep consecutive markdown table rows
    together as a single atomic block (so a field table is never cut in half)."""
    blocks: list[str] = []
    buf: list[str] = []
    in_table = False
    for line in text.split("\n"):
        if _is_table_line(line):
            if not in_table and buf:
                blocks.append("\n".join(buf)); buf = []
            in_table = True
            buf.append(line)
            continue
        if in_table:
            # table ended
            blocks.append("\n".join(buf)); buf = []; in_table = False
        if line.strip() == "":
            if buf:
                blocks.append("\n".join(buf)); buf = []
        else:
            buf.append(line)
    if buf:
        blocks.append("\n".join(buf))
    return [b for b in blocks if b.strip()]


def _split_sections(text: str) -> list[tuple[str, str]]:
    """Split markdown into (heading, body) sections. Returns [("", body)] when the
    text has no headings (e.g. extracted PDF text)."""
    lines = text.split("\n")
    if not any(_HEADING_RE.match(ln) for ln in lines):
        return [("", text)]
    sections: list[tuple[str, str]] = []
    heading = ""
    body: list[str] = []
    for ln in lines:
        if _HEADING_RE.match(ln):
            if heading or body:
                sections.append((heading, "\n".join(body)))
            heading = ln.strip()
            body = []
        else:
            body.append(ln)
    if heading or body:
        sections.append((heading, "\n".join(body)))
    return sections


def chunk_text(text: str, source: str) -> list[Chunk]:
    """Section-aware chunking: split on markdown headings, keep tables whole, and
    pack blocks up to the size limit. Each chunk from a section is prefixed with
    that section's heading so its context survives retrieval. Non-markdown text
    (PDFs) falls back to block packing with overlap."""
    size = settings.chunk_size
    overlap = settings.chunk_overlap
    chunks: list[Chunk] = []
    idx = 0

    for heading, body in _split_sections(text):
        prefix = (heading + "\n\n") if heading else ""
        blocks = _split_blocks(body)
        if not blocks and heading:
            chunks.append(Chunk(text=heading, source=source, chunk_index=idx)); idx += 1
            continue

        buf = ""
        for block in blocks:
            candidate = f"{buf}\n\n{block}" if buf else block
            if len(prefix) + len(candidate) <= size:
                buf = candidate
            else:
                if buf:
                    chunks.append(Chunk(text=(prefix + buf).strip(), source=source, chunk_index=idx)); idx += 1
                    tail = buf[-overlap:] if overlap else ""
                    buf = f"{tail}\n\n{block}" if tail else block
                else:
                    buf = block
                # hard-split a single oversized block (e.g. a huge table)
                while len(prefix) + len(buf) > size:
                    cut = size - len(prefix)
                    chunks.append(Chunk(text=(prefix + buf[:cut]).strip(), source=source, chunk_index=idx)); idx += 1
                    buf = buf[cut - overlap:] if cut - overlap > 0 else buf[cut:]
        if buf.strip():
            chunks.append(Chunk(text=(prefix + buf).strip(), source=source, chunk_index=idx)); idx += 1

    return chunks


def load_and_chunk(path: str) -> list[Chunk]:
    return chunk_text(load_file(path), source=path)


def iter_supported_files(root: str):
    """Yield every supported file under a directory (recursive)."""
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            if os.path.splitext(name)[1].lower() in _LOADERS:
                yield os.path.join(dirpath, name)
