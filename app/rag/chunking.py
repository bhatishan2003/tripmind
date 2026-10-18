"""Chunking: cleaned text -> overlapping chunks for embeddings.

Character-based recursive splitter (no extra dependency):
paragraphs -> sentences -> words, packed with sliding overlap.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.config import settings

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])")
_WORD_SPLIT = re.compile(r"\s+")


@dataclass
class TextChunk:
    chunk_index: int
    content: str
    token_count: int  # rough estimate (~chars/4)


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _hard_split(text: str, max_len: int) -> list[str]:
    """Split an overlong span on word boundaries."""
    words = [w for w in _WORD_SPLIT.split(text) if w]
    parts: list[str] = []
    buf = ""
    for w in words:
        candidate = f"{buf} {w}".strip() if buf else w
        if len(candidate) > max_len and buf:
            parts.append(buf)
            buf = w
        else:
            buf = candidate
    if buf:
        parts.append(buf)
    return parts or [text]


def chunk_text(
    text: str,
    *,
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> list[TextChunk]:
    """Split `text` into overlapping chunks.

    Defaults come from settings (CHUNK_SIZE=800, CHUNK_OVERLAP=150).
    Overlap is implemented as a sliding window over the packed character
    stream so context survives chunk boundaries.
    """
    chunk_size = chunk_size or settings.CHUNK_SIZE
    overlap = overlap if overlap is not None else settings.CHUNK_OVERLAP
    overlap = min(max(overlap, 0), chunk_size // 2)

    text = text.strip()
    if not text:
        return []

    # 1. Break into small spans (paragraphs -> sentences -> words)
    spans: list[str] = []
    for para in re.split(r"\n{2,}", text):
        para = " ".join(para.split())
        if not para:
            continue
        if len(para) <= chunk_size:
            spans.append(para)
            continue
        for sent in _SENTENCE_SPLIT.split(para):
            sent = sent.strip()
            if not sent:
                continue
            spans.extend(_hard_split(sent, chunk_size) if len(sent) > chunk_size else [sent])

    # 2. Pack spans into full-size chunk strings
    packed: list[str] = []
    current = ""
    for span in spans:
        candidate = f"{current}\n\n{span}" if current else span
        if len(candidate) <= chunk_size:
            current = candidate
        else:
            if current:
                packed.append(current)
            current = span
            # span itself is guaranteed <= chunk_size by step 1
    if current:
        packed.append(current)

    # 3. Sliding overlap: prepend tail of previous chunk
    step = max(chunk_size - overlap, 1)
    chunks: list[str] = []
    for i, p in enumerate(packed):
        if i > 0 and overlap > 0 and chunks:
            carry = chunks[-1][-overlap:]
            # Only prepend if it fits; else emit as-is (avoids runaway growth)
            if len(carry) + 2 + len(p) <= chunk_size:
                p = f"{carry}\n\n{p}"
        chunks.append(p)

    # Edge case: single huge packed chunk (shouldn't happen) -> window it
    final: list[str] = []
    for c in chunks:
        if len(c) <= chunk_size:
            final.append(c)
        else:
            for start in range(0, len(c), step):
                final.append(c[start : start + chunk_size])
                if start + chunk_size >= len(c):
                    break

    return [
        TextChunk(chunk_index=i, content=c.strip(), token_count=estimate_tokens(c)) for i, c in enumerate(final) if c.strip()
    ]
