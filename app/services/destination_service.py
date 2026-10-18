"""Destination knowledge-base queries (Phase 2).

Aggregates the ingested `documents` (RAG corpus) into a browsable catalog.
Every function is defensive: with no knowledge base (empty or missing tables)
it returns empty results rather than erroring.
"""

from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.document import Document, DocumentChunk
from app.schemas.destination import DestinationDetail, DestinationDocument, DestinationSummary

logger = logging.getLogger(__name__)


def _snippet(text: str | None, max_len: int = 240) -> str:
    text = " ".join((text or "").split())
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


async def search_destinations(
    session: AsyncSession,
    query: str | None = None,
    *,
    limit: int = 10,
) -> list[DestinationSummary]:
    """Distinct destinations in the corpus, ordered by document count."""
    try:
        stmt = (
            select(Document.destination, Document.category, func.count(Document.id))
            .where(Document.destination.isnot(None))
            .group_by(Document.destination, Document.category)
        )
        if query and query.strip():
            stmt = stmt.where(Document.destination.ilike(f"%{query.strip()}%"))
        rows = (await session.execute(stmt)).all()
    except Exception as exc:  # noqa: BLE001 - no corpus / tables yet
        logger.debug("destination search unavailable: %s", exc)
        return []

    agg: dict[str, DestinationSummary] = {}
    for destination, category, count in rows:
        if not destination:
            continue
        summary = agg.get(destination)
        if summary is None:
            summary = DestinationSummary(destination=destination)
            agg[destination] = summary
        summary.document_count += int(count)
        if category and category not in summary.categories:
            summary.categories.append(category)

    ordered = sorted(agg.values(), key=lambda s: (-s.document_count, s.destination))
    return ordered[:limit]


async def get_destination(session: AsyncSession, name: str) -> DestinationDetail | None:
    """Detail for one destination: its documents with a preview snippet each."""
    name = (name or "").strip()
    if not name:
        return None
    try:
        rows = (
            await session.execute(
                select(Document, DocumentChunk.content)
                .outerjoin(
                    DocumentChunk,
                    (DocumentChunk.document_id == Document.id) & (DocumentChunk.chunk_index == 0),
                )
                .where(Document.destination.ilike(name))
                .order_by(Document.title)
            )
        ).all()
    except Exception as exc:  # noqa: BLE001 - no corpus / tables yet
        logger.debug("destination lookup unavailable: %s", exc)
        return None

    if not rows:
        return None

    documents: list[DestinationDocument] = []
    categories: list[str] = []
    for doc, first_chunk in rows:
        if doc.category and doc.category not in categories:
            categories.append(doc.category)
        documents.append(
            DestinationDocument(
                id=str(doc.id),
                title=doc.title,
                source_uri=doc.source_uri,
                category=doc.category,
                snippet=_snippet(first_chunk),
            )
        )

    # Prefer the corpus' canonical casing for the destination label.
    canonical = rows[0][0].destination or name
    return DestinationDetail(
        destination=canonical,
        document_count=len(documents),
        categories=categories,
        documents=documents,
    )
