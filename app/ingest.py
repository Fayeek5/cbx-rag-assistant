"""Document loading and chunking.

Supports .md, .txt, .pdf, .docx. Chunks by paragraph with a target size and
overlap, so a single chunk keeps related sentences together but neighbouring
chunks share context at their edges (helps retrieval recall).
"""
from __future__ import annotations

import os
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
def chunk_text(text: str, source: str) -> list[Chunk]:
    """Greedy paragraph packing with character overlap."""
    size = settings.chunk_size
    overlap = settings.chunk_overlap

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[Chunk] = []
    buf = ""
    idx = 0

    def flush():
        nonlocal buf, idx
        if buf.strip():
            chunks.append(Chunk(text=buf.strip(), source=source, chunk_index=idx))
            idx += 1

    for para in paragraphs:
        if len(buf) + len(para) + 2 <= size:
            buf = f"{buf}\n\n{para}" if buf else para
        else:
            flush()
            # carry the tail of the previous chunk as overlap
            tail = buf[-overlap:] if overlap and buf else ""
            buf = f"{tail}\n\n{para}" if tail else para
            # a single oversized paragraph: hard-split it
            while len(buf) > size:
                chunks.append(Chunk(text=buf[:size].strip(), source=source, chunk_index=idx))
                idx += 1
                buf = buf[size - overlap:]
    flush()
    return chunks


def load_and_chunk(path: str) -> list[Chunk]:
    return chunk_text(load_file(path), source=path)


def iter_supported_files(root: str):
    """Yield every supported file under a directory (recursive)."""
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            if os.path.splitext(name)[1].lower() in _LOADERS:
                yield os.path.join(dirpath, name)
