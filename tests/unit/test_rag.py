"""Phase 2 RAG unit tests — offline, no API keys, no Postgres needed."""

from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.database import Base
from app.rag.chunking import chunk_text
from app.rag.cleaning import clean_text, should_keep
from app.rag.embeddings import cosine_similarity, embed_texts
from app.rag.ingest import RawDocument, ingest_directory


def test_clean_text_normalizes():
    assert clean_text("<p>Hello   <b>Kyoto</b></p>\n\n\nGion.") == "Hello Kyoto\n\nGion."
    assert not should_keep("  hi  ")
    assert should_keep("Gion is the famous geisha district of Kyoto with machiya streets.")


def test_chunk_text_overlap_and_indices():
    text = "Para one about Gion. " * 40 + "\n\n" + "Para two about Arashiyama. " * 40
    chunks = chunk_text(text, chunk_size=800, overlap=150)
    assert len(chunks) >= 2
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
    assert all(len(c.content) <= 800 for c in chunks)


def test_ingest_sample_kyoto_doc():
    docs = ingest_directory(Path("data/documents"))
    uris = [d.source_uri for d in docs]
    assert any("kyoto" in u.lower() for u in uris)
    kyoto = next(d for d in docs if "kyoto" in d.source_uri.lower())
    assert kyoto.destination == "Kyoto"
    assert kyoto.checksum and len(kyoto.content) > 200


def test_embeddings_returns_config_dim():
    from app.core.config import settings

    vecs = embed_texts(["Gion geisha district", "Arashiyama bamboo grove"])
    assert len(vecs) == 2
    assert len(vecs[0]) == settings.EMBEDDING_DIM
    # Self-similarity is 1.0 for normalized vectors
    assert cosine_similarity(vecs[0], vecs[0]) == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_store_roundtrip_and_filtered_search():
    import app.db.models  # noqa: F401 (register tables)
    from app.rag.store import semantic_search, upsert_document

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    raw = RawDocument(
        source_uri="test/kyoto.md",
        title="Kyoto Guide",
        destination="Kyoto",
        category="areas-to-stay",
        checksum="abc",
        content="Gion is best for traditional culture. " * 20,
    )
    async with Session() as s:
        doc = await upsert_document(s, raw)
        assert doc.id is not None
        # Re-ingest same checksum -> dedupe, no duplicate chunks
        await upsert_document(s, raw)
        hits = await semantic_search(
            s,
            "best areas to stay in Kyoto for traditional culture?",
            top_k=3,
            filters={"destination": "Kyoto"},
        )
    await engine.dispose()
    assert hits, "Kyoto query must retrieve at least one chunk"
    assert all(h.source_uri and h.chunk_id and h.document_id for h in hits)
