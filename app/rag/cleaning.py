"""Travel document cleaning: raw text -> normalized, searchable text.

Covers the 'Cleaning' stage of the pipeline:
    Travel documents -> Cleaning -> Chunking -> Embeddings -> pgvector
"""

from __future__ import annotations

import re
import unicodedata

_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_MULTI_BLANK_RE = re.compile(r"\n{3,}")
_WS_RE = re.compile(r"[ \t]+")
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def strip_html(text: str) -> str:
    """Remove HTML tags. Tries BeautifulSoup when installed, else regex."""
    try:
        from bs4 import BeautifulSoup  # type: ignore

        return BeautifulSoup(text, "html.parser").get_text(separator="\n")
    except ImportError:
        return _HTML_TAG_RE.sub(" ", text)


def clean_text(text: str, *, strip_html_tags: bool = True) -> str:
    """Normalize unicode, whitespace and control chars."""
    if not text:
        return ""
    if strip_html_tags and "<" in text and ">" in text:
        text = strip_html(text)
    text = unicodedata.normalize("NFKC", text)
    text = _CONTROL_RE.sub(" ", text)
    # Normalize line endings, collapse horizontal whitespace
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [_WS_RE.sub(" ", ln).strip() for ln in text.split("\n")]
    text = "\n".join(lines)
    text = _MULTI_BLANK_RE.sub("\n\n", text)
    return text.strip()


def should_keep(text: str, min_chars: int = 50) -> bool:
    """Drop boilerplate / tiny fragments before chunking."""
    if len(text.strip()) < min_chars:
        return False
    # Drop pages that are mostly numbers/punctuation (e.g. PDF junk)
    alnum = sum(c.isalnum() for c in text)
    return alnum / max(len(text), 1) > 0.3


def extract_title(content: str, fallback: str) -> str:
    """First markdown `# ` heading, else filename stem prettified."""
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()[:512]
    return fallback.replace("_", " ").replace("-", " ").strip().title()[:512]
