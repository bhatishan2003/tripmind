"""Document ingestion: data/documents (.md/.txt/.pdf) -> cleaned RawDocuments.

Filename/subdirectory conventions for metadata (all optional):
    data/documents/<destination>/<file>.md        -> destination from folder
    data/documents/<destination>__<category>__*.md -> destination + category
Front-matter `destination: X` / `category: Y` lines are also honored.
Dedupe via SHA256 checksum (re-ingest skips unchanged files).
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from app.core.config import settings
from app.rag.cleaning import clean_text, extract_title, should_keep

logger = logging.getLogger(__name__)

SUPPORTED_SUFFIXES = {".md", ".markdown", ".txt", ".pdf"}
_FRONTMATTER_RE = re.compile(r"^(destination|category|title|language)\s*:\s*(.+)$", re.IGNORECASE)


@dataclass
class RawDocument:
    source_uri: str  # stable id, e.g. "kyoto/areas-to-stay.md"
    title: str
    destination: str | None
    category: str | None
    language: str = "en"
    checksum: str = ""
    content: str = ""  # cleaned text
    metadata: dict = field(default_factory=dict)


def _read_file(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        return "\n\n".join((page.extract_text() or "") for page in reader.pages)
    return path.read_text(encoding="utf-8", errors="replace")


def _infer_from_path(path: Path, root: Path) -> tuple[str | None, str | None]:
    """Infer (destination, category) from path parts and __ separators."""
    try:
        rel_parent = path.relative_to(root).parent
        folder_dest = rel_parent.parts[0] if rel_parent.parts else None
    except ValueError:
        folder_dest = None
    dest: str | None = folder_dest
    cat: str | None = None
    # "__" convention: <destination>__<category>__<rest>
    segments = [s.strip() for s in path.stem.split("__") if s.strip()]
    if len(segments) >= 2:
        dest, cat = segments[0], segments[1]
    elif len(rel_parent.parts) >= 2:
        cat = rel_parent.parts[1]
    return dest, cat


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Pull leading `key: value` lines out of the text."""
    meta: dict = {}
    body_lines = text.splitlines()
    consumed = 0
    for line in body_lines:
        m = _FRONTMATTER_RE.match(line.strip())
        if m:
            meta[m.group(1).lower()] = m.group(2).strip()
            consumed += 1
        elif not line.strip():
            consumed += 1  # skip blank lines inside front-matter block
        else:
            break
    body = "\n".join(body_lines[consumed:]) if consumed else text
    return meta, body


def ingest_file(path: Path, root: Path | None = None) -> RawDocument | None:
    """Ingest one file; returns None when content is unusable."""
    root = root or Path(settings.RAG_DATA_DIR)
    raw = _read_file(path)
    meta, body = _parse_frontmatter(raw)
    cleaned = clean_text(body)
    if not should_keep(cleaned):
        return None

    try:
        source_uri = path.relative_to(root).as_posix()
    except ValueError:
        source_uri = path.name

    checksum = hashlib.sha256(cleaned.encode("utf-8")).hexdigest()
    path_dest, path_cat = _infer_from_path(path, root)
    title = meta.get("title") or extract_title(raw, path.stem)

    # Normalize destination like "kyoto" -> "Kyoto"
    def _norm(v: str | None) -> str | None:
        return v.strip().title() if v and v.strip() else None

    destination = _norm(meta.get("destination") or path_dest)
    category = (meta.get("category") or path_cat or "").strip().lower() or None

    return RawDocument(
        source_uri=source_uri,
        title=title,
        destination=destination,
        category=category,
        language=meta.get("language", "en"),
        checksum=checksum,
        content=cleaned,
        metadata={"file": path.name, **{k: v for k, v in meta.items() if k not in {"title", "destination", "category"}}},
    )


def ingest_directory(root: str | Path | None = None) -> list[RawDocument]:
    """Ingest every supported file under `root` (sorted for determinism)."""
    root_path = Path(root or settings.RAG_DATA_DIR)
    if not root_path.exists():
        return []
    docs: list[RawDocument] = []
    for path in sorted(root_path.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        if path.name.startswith("."):
            continue
        try:
            doc = ingest_file(path, root_path)
        except Exception as exc:  # noqa: BLE001 - one bad file must not kill the batch
            logger.debug("Skipping %s: %s", path, exc)
            continue
        if doc is not None:
            docs.append(doc)
    return docs
