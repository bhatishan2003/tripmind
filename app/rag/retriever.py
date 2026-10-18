"""High-level retrieval used by itinerary generation and the destinations API.

Thin, defensive layer over `app.rag.store.semantic_search`:
- builds a natural-language query from trip constraints (destination + interests)
- filters by destination first, then widens the search if nothing matches
- never raises: a missing/empty knowledge base simply yields no context
"""

from __future__ import annotations

import logging

from app.core.config import settings
from app.rag.store import SearchHit, semantic_search
from app.schemas.itinerary import ItinerarySource

logger = logging.getLogger(__name__)

_DEFAULT_MAX_SNIPPET = 280


def build_query(destination: str, interests: list[str] | None = None) -> str:
    """Compose a retrieval query from a trip's destination and interests."""
    parts = [destination.strip()] if destination and destination.strip() else []
    if interests:
        parts.append(", ".join(i for i in interests if i))
    parts.append("travel guide highlights things to do where to stay local food")
    return " ".join(parts).strip()


def _snippet(text: str, max_len: int = _DEFAULT_MAX_SNIPPET) -> str:
    text = " ".join((text or "").split())
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def hits_to_sources(hits: list[SearchHit], *, unique_by_source: bool = True) -> list[ItinerarySource]:
    """Convert raw search hits into citation-friendly sources (one per document)."""
    sources: list[ItinerarySource] = []
    seen: set[str] = set()
    for hit in hits:
        if unique_by_source and hit.source_uri in seen:
            continue
        seen.add(hit.source_uri)
        sources.append(
            ItinerarySource(
                title=hit.title,
                source_uri=hit.source_uri,
                destination=hit.destination,
                category=hit.category,
                snippet=_snippet(hit.content),
                score=round(float(hit.score), 4),
            )
        )
    return sources


async def retrieve_context(
    session,  # type: ignore[no-untyped-def]
    *,
    destination: str,
    interests: list[str] | None = None,
    top_k: int | None = None,
) -> list[SearchHit]:
    """Best-effort semantic retrieval for a trip; returns [] on any failure."""
    query = build_query(destination, interests)
    top_k = top_k or settings.RAG_TOP_K
    try:
        hits = await semantic_search(session, query, top_k=top_k, filters={"destination": destination})
        if not hits:
            # Destination label may differ from the stored one (e.g. "Kyoto, Japan")
            hits = await semantic_search(session, query, top_k=top_k, filters=None)
        return hits
    except Exception as exc:  # noqa: BLE001 - knowledge base is optional infrastructure
        logger.warning("Retrieval unavailable (%s) — generating without RAG context", exc)
        return []


async def retrieve_sources(
    session,  # type: ignore[no-untyped-def]
    *,
    destination: str,
    interests: list[str] | None = None,
    top_k: int | None = None,
) -> list[ItinerarySource]:
    """Retrieve context and shape it as citable sources."""
    hits = await retrieve_context(session, destination=destination, interests=interests, top_k=top_k)
    return hits_to_sources(hits)
