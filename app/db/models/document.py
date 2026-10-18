"""Phase 2 RAG documents — pgvector-backed, SQLite-compatible for tests.

Postgres: `embedding` uses pgvector `vector(dim)` + HNSW index (see migration).
SQLite (tests/local fallback): same column degrades to JSON list[float].
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, String, Text, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from app.core.config import settings
from app.db.database import Base


class EmbeddingVector(TypeDecorator):
    """Use pgvector on Postgres, plain JSON list on other dialects (SQLite tests)."""

    impl = JSON
    cache_ok = True

    def __init__(self, dim: int | None = None, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.dim = dim or settings.EMBEDDING_DIM

    def load_dialect_impl(self, dialect):  # type: ignore[no-untyped-def]
        if dialect.name == "postgresql":
            from pgvector.sqlalchemy import Vector

            return Vector(self.dim)
        return JSON()

    def process_bind_param(self, value, dialect):  # type: ignore[no-untyped-def]
        if value is None:
            return None
        # Normalize numpy arrays / tuples to plain float lists for both backends.
        if hasattr(value, "tolist"):
            value = value.tolist()
        if isinstance(value, (tuple, list)):
            return [float(x) for x in value]
        return value

    def process_result_value(self, value, dialect):  # type: ignore[no-untyped-def]
        if value is None:
            return None
        if isinstance(value, str):
            # pgvector may return "[0.1,0.2,...]" in some drivers
            value = value.strip().lstrip("[").rstrip("]")
            if not value:
                return []
            return [float(x) for x in value.split(",")]
        if hasattr(value, "tolist"):
            return [float(x) for x in value.tolist()]
        if isinstance(value, (list, tuple)):
            return [float(x) for x in value]
        return value


# Metadata columns: JSONB on Postgres (for @> filtering), JSON elsewhere.
MetadataJSON = JSONB().with_variant(JSON(), "sqlite")


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
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))

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
    embedding: Mapped[list[float] | None] = mapped_column(EmbeddingVector(), nullable=True)
    chunk_metadata: Mapped[dict] = mapped_column(MetadataJSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))

    document: Mapped["Document"] = relationship("Document", back_populates="chunks")
