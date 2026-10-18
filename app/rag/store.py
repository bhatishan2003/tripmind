"""pgvector persistence + semantic search (works on Postgres and SQLite).

Postgres path:  embedding <=> query_vector cosine operator + metadata filters.
SQLite path (tests): loads candidate chunks, scores with pure-python cosine.
Source tracking: every hit returns document_id / chunk_id / source_uri / score.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import delete, select

from app.db.models.document import Document, DocumentChunk
from app.rag.chunking import chunk_text
from app.rag.embeddings import cosine_similarity, embed_query, embed_texts
from app.rag.ingest import RawDocument

logger = logging.getLogger(__name__)


@dataclass
class SearchHit:
    content: str
    score: float
    document_id: str
    chunk_id: str
    source_uri: str
    title: str
    destination: str | None
    category: str | None


def _dialect_name(session) -> str:  # type: ignore[no-untyped-def]
    """Best-effort dialect name for AsyncSession (AsyncEngine) or sync Session."""
    try:
        bind = session.get_bind() if hasattr(session, "get_bind") else session.bind
        if bind is None:
            return "sqlite"
        url = getattr(bind, "url", None)
        if url is not None:
            return str(getattr(url, "drivername", "")).split("+")[0] or "sqlite"
        dialect = getattr(bind, "dialect", None) or getattr(getattr(bind, "sync_engine", None), "dialect", None)
        if dialect is not None:
            return getattr(dialect, "name", "sqlite")
    except Exception:  # noqa: BLE001, S110 - Postgres-only, SQLite skips
        pass
    return "sqlite"


async def ensure_vector_extension(session) -> None:  # type: ignore[no-untyped-def]
    """CREATE EXTENSION vector on Postgres; silently skip on SQLite/tests."""
    try:
        await session.execute(__import__("sqlalchemy").text("CREATE EXTENSION IF NOT EXISTS vector"))
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        logger.debug("vector extension not available: %s", exc)


async def upsert_document(session, raw: RawDocument) -> Document:  # type: ignore[no-untyped-def]
    """Insert/update a Document + its chunks/embeddings. Skips unchanged docs."""
    existing = (await session.execute(select(Document).where(Document.source_uri == raw.source_uri))).scalars().first()
    if existing is not None and existing.checksum == raw.checksum:
        return existing  # dedupe: nothing changed

    if existing is None:
        doc = Document(
            source_uri=raw.source_uri,
            title=raw.title,
            destination=raw.destination,
            category=raw.category,
            language=raw.language,
            checksum=raw.checksum,
            doc_metadata=raw.metadata,
        )
        session.add(doc)
        await session.flush()
    else:
        doc = existing
        doc.title = raw.title
        doc.destination = raw.destination
        doc.category = raw.category
        doc.checksum = raw.checksum
        doc.doc_metadata = raw.metadata
        await session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == doc.id))
        await session.flush()

    text_chunks = chunk_text(raw.content)
    vectors = embed_texts([c.content for c in text_chunks])
    for tc, vec in zip(text_chunks, vectors):
        session.add(
            DocumentChunk(
                document_id=doc.id,
                chunk_index=tc.chunk_index,
                content=tc.content,
                token_count=tc.token_count,
                embedding=list(vec),
                chunk_metadata={
                    "source_uri": raw.source_uri,
                    "title": raw.title,
                    "destination": raw.destination,
                    "category": raw.category,
                },
            )
        )
    await session.commit()
    await session.refresh(doc)
    return doc


def _matches(chunk: DocumentChunk, filters: dict) -> bool:
    meta = chunk.chunk_metadata or {}
    for key in ("destination", "category"):
        if filters.get(key) and (meta.get(key) or "").lower() != str(filters[key]).lower():
            doc_val = getattr(chunk.document, key, None) if hasattr(chunk, "document") else None
            if not doc_val or str(doc_val).lower() != str(filters[key]).lower():
                return False
    return True


async def semantic_search(  # type: ignore[no-untyped-def]
    session,
    query: str,
    *,
    top_k: int = 5,
    filters: dict | None = None,
) -> list[SearchHit]:
    """Top-k chunks for `query`, optionally filtered by destination/category."""
    from app.core.config import settings

    filters = filters or {}
    top_k = top_k or settings.RAG_TOP_K
    query_vec = embed_query(query)

    dialect = _dialect_name(session)
    if dialect == "postgresql":
        # pgvector cosine distance: smaller <=> is more similar
        distance = DocumentChunk.embedding.cosine_distance(query_vec)  # type: ignore[attr-defined]
        stmt = (
            select(DocumentChunk, Document, distance.label("distance"))
            .join(Document, Document.id == DocumentChunk.document_id)
            .order_by(distance)
            .limit(top_k * 3)  # over-fetch, then apply metadata filter in Python
        )
        rows = (await session.execute(stmt)).all()
        hits: list[SearchHit] = []
        for chunk, doc, dist in rows:
            if not _matches(chunk, filters):
                continue
            hits.append(
                SearchHit(
                    content=chunk.content,
                    score=float(1.0 / (1.0 + float(dist))),
                    document_id=str(doc.id),
                    chunk_id=str(chunk.id),
                    source_uri=doc.source_uri,
                    title=doc.title,
                    destination=doc.destination,
                    category=doc.category,
                )
            )
            if len(hits) >= top_k:
                break
        return hits

    # SQLite / test fallback: brute-force cosine in Python
    stmt = select(DocumentChunk, Document).join(Document, Document.id == DocumentChunk.document_id)
    if filters.get("destination"):
        stmt = stmt.where(Document.destination == filters["destination"])
    if filters.get("category"):
        stmt = stmt.where(Document.category == filters["category"])
    rows = (await session.execute(stmt)).all()
    scored: list[SearchHit] = []
    for chunk, doc in rows:
        if chunk.embedding is None:
            continue
        if not _matches(chunk, filters):
            continue
        scored.append(
            SearchHit(
                content=chunk.content,
                score=cosine_similarity(query_vec, list(chunk.embedding)),
                document_id=str(doc.id),
                chunk_id=str(chunk.id),
                source_uri=doc.source_uri,
                title=doc.title,
                destination=doc.destination,
                category=doc.category,
            )
        )
    scored.sort(key=lambda h: h.score, reverse=True)
    return scored[:top_k]
