"""Phase 2 retriever tests — offline, SQLite, no API keys."""

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.database import Base
from app.rag.ingest import RawDocument
from app.rag.retriever import build_query, hits_to_sources, retrieve_sources
from app.rag.store import SearchHit, upsert_document

KYOTO = (
    "Gion is the famous geisha district of Kyoto, best for traditional culture, "
    "machiya streets and tea houses. Higashiyama has temples on your doorstep. "
) * 6


def test_build_query_includes_destination_and_interests():
    query = build_query("Kyoto", ["culture", "food"])
    assert "Kyoto" in query
    assert "culture" in query and "food" in query


def test_hits_to_sources_dedupes_and_shapes():
    hits = [
        SearchHit("x" * 400, 0.9, "d1", "c1", "kyoto/a.md", "T1", "Kyoto", "areas"),
        SearchHit("y", 0.8, "d1", "c2", "kyoto/a.md", "T1", "Kyoto", "areas"),
        SearchHit("z", 0.7, "d2", "c3", "kyoto/b.md", "T2", "Kyoto", "food"),
    ]
    sources = hits_to_sources(hits)
    assert [s.source_uri for s in sources] == ["kyoto/a.md", "kyoto/b.md"]
    assert sources[0].snippet.endswith("…")
    assert sources[0].score == 0.9


@pytest.mark.asyncio
async def test_retrieve_sources_from_corpus():
    import app.db.models  # noqa: F401 (register tables)

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    raw = RawDocument(
        source_uri="kyoto/areas.md",
        title="Where to Stay in Kyoto",
        destination="Kyoto",
        category="areas-to-stay",
        checksum="sum1",
        content=KYOTO,
    )
    async with Session() as s:
        await upsert_document(s, raw)
        sources = await retrieve_sources(s, destination="Kyoto", interests=["culture"])
    await engine.dispose()

    assert sources, "Kyoto corpus must yield at least one source"
    assert sources[0].title == "Where to Stay in Kyoto"
    assert sources[0].destination == "Kyoto"
    assert sources[0].snippet


@pytest.mark.asyncio
async def test_retrieve_sources_empty_corpus_is_graceful():
    import app.db.models  # noqa: F401 (register tables)

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as s:
        sources = await retrieve_sources(s, destination="Nowhere", interests=["food"])
    await engine.dispose()
    assert sources == []
