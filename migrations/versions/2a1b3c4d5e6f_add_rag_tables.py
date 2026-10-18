"""Add RAG knowledge base tables (documents + document_chunks with pgvector).

Revision ID: 2a1b3c4d5e6f
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "2a1b3c4d5e6f"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # pgvector extension (Postgres only — no-op on other backends)
    try:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    except Exception:  # noqa: BLE001, S110 - best-effort: not available on SQLite/other backends
        pass

    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("source_uri", sa.String(1024), unique=True, nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("destination", sa.String(255), nullable=True, index=True),
        sa.Column("category", sa.String(128), nullable=True, index=True),
        sa.Column("language", sa.String(16), server_default="en"),
        sa.Column("checksum", sa.String(64), nullable=True, index=True),
        sa.Column("doc_metadata", postgresql.JSONB(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )

    # NOTE: embedding column type is pgvector VECTOR(384) on Postgres.
    # pgvector.sqlalchemy.Vector is imported lazily so SQLite/autogenerate stays happy.
    try:
        from pgvector.sqlalchemy import Vector

        vector_type = Vector(384)
    except ImportError:  # pragma: no cover - fallback if pgvector missing
        vector_type = sa.JSON()

    op.create_table(
        "document_chunks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("document_id", sa.Uuid(), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("embedding", vector_type, nullable=True),
        sa.Column("chunk_metadata", postgresql.JSONB(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("document_id", "chunk_index", name="uq_chunk_doc_idx"),
    )

    # HNSW cosine index for semantic search (Postgres + pgvector only)
    try:
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_chunks_embedding_hnsw ON document_chunks USING hnsw (embedding vector_cosine_ops)"
        )
        op.execute("CREATE INDEX IF NOT EXISTS ix_chunks_metadata_gin ON document_chunks USING gin (chunk_metadata)")
    except Exception:  # noqa: BLE001, S110 - best-effort: index types require pgvector/Postgres
        pass


def downgrade() -> None:
    op.drop_table("document_chunks")
    op.drop_table("documents")
