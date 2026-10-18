"""Phase 2 RAG documents — pgvector-backed, SQLite-compatible for tests.

Postgres: `embedding` uses pgvector `vector(dim)` (exposes cosine_distance).
SQLite (tests/local fallback): the same column degrades to JSON list[float].

`Vector(...).with_variant(JSON(), "sqlite")` is used instead of a TypeDecorator
because a TypeDecorator hides pgvector's distance comparators, which broke
`DocumentChunk.embedding.cosine_distance(...)` on Postgres.
"""

import uuid
from datetime import UTC, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
from app.db.database import Base

# Metadata columns: JSONB on Postgres (for @> filtering), JSON elsewhere.
MetadataJSON = JSONB().with_variant(JSON(), "sqlite")

# Embeddings: pgvector on Postgres (enables cosine_distance), JSON on SQLite.
EmbeddingColumn = Vector(settings.EMBEDDING_DIM).with_variant(JSON(), "sqlite")


class Document(Base):
    """A raw ingested travel document (one file / one source URI)."""

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source_uri: Mapped[str] = mapped_column(String(1024), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    destination: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    category: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    language: Mapped[str] = mapped_column(String(16), default="en")
    checksum: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    doc_metadata: Mapped[dict] = mapped_column(MetadataJSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    chunks: Mapped[list["DocumentChunk"]] = relationship(
        "DocumentChunk", back_populates="document", cascade="all, delete-orphan"
    )


class DocumentChunk(Base):
    """One embedding-ready chunk with source tracking back to Document."""

    __tablename__ = "document_chunks"
    __table_args__ = (UniqueConstraint("document_id", "chunk_index", name="uq_chunk_doc_idx"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(nullable=False, default=0)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int | None] = mapped_column(nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(EmbeddingColumn, nullable=True)
    chunk_metadata: Mapped[dict] = mapped_column(MetadataJSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    document: Mapped["Document"] = relationship("Document", back_populates="chunks")
