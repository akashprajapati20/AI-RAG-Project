"""Ingestion pipeline: file -> sections -> chunks -> embeddings -> Postgres."""

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from psycopg.types.json import Jsonb

from app.chunking import Chunk, chunk_document
from app.config import PROJECT_ROOT, get_settings
from app.db import get_pool
from app.embeddings import embed_documents
from app.loaders import LOADERS, LoadedDocument, load_document

# Bump when loader or chunker logic changes, so every document is re-processed on the next run.
PIPELINE_VERSION = 5


@dataclass
class IngestResult:
    source: str
    status: str  # "added" | "updated" | "unchanged" | "failed"
    chunks: int = 0
    error: str | None = None


def ingest_directory(directory: Path, force: bool = False) -> list[IngestResult]:
    files = sorted(p for p in directory.rglob("*") if p.is_file() and p.suffix.lower() in LOADERS)
    results = []
    for path in files:
        try:
            results.append(ingest_file(path, force=force))
        except Exception as e:  # keep going; one bad file shouldn't stop the batch
            results.append(IngestResult(source_id(path), "failed", error=f"{type(e).__name__}: {e}"))
    return results


def ingest_file(path: Path, force: bool = False) -> IngestResult:
    source = source_id(path)
    content_hash = fingerprint(path)

    with get_pool().connection() as conn:
        row = conn.execute("SELECT content_hash FROM documents WHERE source = %s", (source,)).fetchone()
    if row and row[0] == content_hash and not force:
        return IngestResult(source, "unchanged")

    doc, chunks = prepare(path)
    # Prefix the document title so a chunk like "4. SLA credits ..." is embedded as being
    # about Tally pricing. The stored content stays clean for display and citations.
    vectors = embed_documents([f"{doc.title}\n\n{chunk.text}" for chunk in chunks])

    metadata = {**doc.metadata, "ingested_at": datetime.now(timezone.utc).isoformat()}
    with get_pool().connection() as conn, conn.transaction():
        document_id = conn.execute(
            """
            INSERT INTO documents (source, title, content_hash, metadata)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (source) DO UPDATE
                SET title = EXCLUDED.title, content_hash = EXCLUDED.content_hash, metadata = EXCLUDED.metadata
            RETURNING id
            """,
            (source, doc.title, content_hash, Jsonb(metadata)),
        ).fetchone()[0]
        conn.execute("DELETE FROM chunks WHERE document_id = %s", (document_id,))
        # tsv (keyword index) gets the title too, at normal weight: boosting it (setweight 'B'/'C')
        # over-rewarded generic title words like "plan" and lowered hybrid MRR in our spot-check.
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO chunks (document_id, chunk_index, content, embedding, metadata, tsv)
                VALUES (%s, %s, %s, %s, %s, to_tsvector('english', %s) || to_tsvector('english', %s))
                """,
                [
                    (document_id, i, chunk.text, vector, Jsonb(chunk.metadata), doc.title, chunk.text)
                    for i, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True))
                ],
            )

    return IngestResult(source, "updated" if row else "added", chunks=len(chunks))


def prepare(path: Path) -> tuple[LoadedDocument, list[Chunk]]:
    """Load and chunk a file without touching the API or database (also used for --dry-run)."""
    settings = get_settings()
    doc = load_document(path)
    return doc, chunk_document(doc, settings.chunk_size, settings.chunk_overlap)


def prune(directory: Path, keep: set[str]) -> list[str]:
    """Delete documents from `directory` whose files no longer exist. Returns their sources."""
    with get_pool().connection() as conn:
        rows = conn.execute(
            "DELETE FROM documents WHERE starts_with(source, %s) AND source <> ALL(%s) RETURNING source",
            (source_id(directory).rstrip("/") + "/", list(keep)),
        ).fetchall()
    return [r[0] for r in rows]


def source_id(path: Path) -> str:
    """Stable identifier for a file: its path relative to the project root when possible."""
    path = path.resolve()
    try:
        return path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def fingerprint(path: Path) -> str:
    """Hash of the file plus every setting that affects its chunks or embeddings,
    so changing chunk size or embedding model also triggers re-ingestion."""
    s = get_settings()
    settings_key = f"{PIPELINE_VERSION}|{s.embedding_model}|{s.embedding_dim}|{s.chunk_size}|{s.chunk_overlap}"
    return hashlib.sha256(path.read_bytes() + settings_key.encode()).hexdigest()
