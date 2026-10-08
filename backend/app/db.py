"""Postgres + pgvector: schema management and a shared connection pool."""

import atexit
from functools import lru_cache

import psycopg
from pgvector.psycopg import register_vector
from psycopg_pool import ConnectionPool

from app.config import get_settings


def _schema_sql(dim: int) -> str:
    return f"""
    CREATE TABLE IF NOT EXISTS documents (
        id           BIGSERIAL PRIMARY KEY,
        source       TEXT NOT NULL UNIQUE,              -- file path / URL the document came from
        title        TEXT,
        content_hash TEXT NOT NULL,                     -- lets ingestion skip unchanged files
        metadata     JSONB NOT NULL DEFAULT '{{}}',
        created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    CREATE TABLE IF NOT EXISTS chunks (
        id          BIGSERIAL PRIMARY KEY,
        document_id BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
        chunk_index INT NOT NULL,                       -- position within the document
        content     TEXT NOT NULL,
        embedding   vector({dim}) NOT NULL,
        -- Keyword-search vector for hybrid search: document title + chunk text, written at
        -- ingest time so a chunk is findable by its document's title too (e.g. "INC-2026-031").
        tsv         tsvector NOT NULL,
        metadata    JSONB NOT NULL DEFAULT '{{}}',       -- e.g. page number, section heading
        UNIQUE (document_id, chunk_index)
    );

    -- Approximate nearest-neighbour index for cosine-similarity search.
    CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw ON chunks USING hnsw (embedding vector_cosine_ops);
    -- Inverted index for full-text search.
    CREATE INDEX IF NOT EXISTS chunks_tsv_gin ON chunks USING gin (tsv);
    """


def init_schema(reset: bool = False) -> None:
    """Create the pgvector extension and tables. Safe to run repeatedly.

    reset=True drops the tables first, deleting all ingested data.
    """
    settings = get_settings()
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        if reset:
            conn.execute("DROP TABLE IF EXISTS chunks, documents CASCADE")
        conn.execute(_schema_sql(settings.embedding_dim))
        # Migration: tables created before Part 3 had tsv as a generated column (chunk text only).
        # Turn it into a normal column; re-ingesting then fills in the title-aware version.
        conn.execute("ALTER TABLE chunks ALTER COLUMN tsv DROP EXPRESSION IF EXISTS")

        # For a vector column, atttypmod holds its dimension.
        existing_dim = conn.execute(
            "SELECT atttypmod FROM pg_attribute "
            "WHERE attrelid = 'chunks'::regclass AND attname = 'embedding'"
        ).fetchone()[0]
        if existing_dim != settings.embedding_dim:
            raise RuntimeError(
                f"chunks.embedding is vector({existing_dim}) but EMBEDDING_DIM={settings.embedding_dim}. "
                "Run `python -m scripts.init_db --reset` (deletes ingested data) to rebuild the table."
            )


@lru_cache
def get_pool() -> ConnectionPool:
    """Shared connection pool. Every connection can send/receive pgvector values as numpy arrays.

    Call init_schema() first: registering the vector type needs the extension to exist.
    """
    pool = ConnectionPool(
        get_settings().database_url,
        min_size=1,
        max_size=10,
        configure=register_vector,
        open=True,
    )
    # Close before interpreter shutdown; otherwise the pool's worker threads can't be joined.
    atexit.register(pool.close)
    return pool
