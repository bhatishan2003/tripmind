"""CLI: ingest data/documents -> chunk -> embed -> pgvector.

Usage:
    python scripts/ingest_knowledge.py
    python scripts/ingest_knowledge.py --source data/documents --destination Kyoto
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ingest")


async def _run(source: Path, dest_filter: str | None) -> int:
    from sqlalchemy import text

    from app.db.database import AsyncSessionLocal, Base, engine
    from app.db.models import document as _document_models  # noqa: F401 (register tables)
    from app.rag.ingest import ingest_directory
    from app.rag.store import ensure_vector_extension, upsert_document

    # Local dev: create tables if missing (Alembic covers production).
    # The pgvector extension must exist *before* create_all, or the
    # `embedding vector(dim)` column DDL fails on a fresh database.
    async with engine.begin() as conn:
        if conn.dialect.name == "postgresql":
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)

    docs = ingest_directory(source)
    if dest_filter:
        docs = [d for d in docs if (d.destination or "").lower() == dest_filter.lower()]
    logger.info("Found %d usable document(s) in %s", len(docs), source)

    count_chunks = 0
    async with AsyncSessionLocal() as session:
        await ensure_vector_extension(session)
        for raw in docs:
            await upsert_document(session, raw)
            logger.info("Upserted %-40s dest=%s", raw.source_uri, raw.destination)
            count_chunks += 1
    await engine.dispose()
    logger.info("Done: %d document(s).", count_chunks)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest travel docs into pgvector")
    parser.add_argument("--source", default="data/documents")
    parser.add_argument("--destination", default=None, help="only ingest this destination")
    args = parser.parse_args()
    return asyncio.run(_run(Path(args.source), args.destination))


if __name__ == "__main__":
    raise SystemExit(main())
