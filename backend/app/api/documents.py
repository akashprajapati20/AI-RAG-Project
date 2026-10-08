"""List, upload and delete knowledge-base documents."""

import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile

from app.api.schemas import DocumentInfo, UploadResult
from app.config import PROJECT_ROOT
from app.db import get_pool
from app.ingest import ingest_file
from app.loaders import LOADERS

router = APIRouter(tags=["documents"])

UPLOAD_DIR = PROJECT_ROOT / "data" / "uploads"
MAX_UPLOAD_BYTES = 20 * 1024 * 1024


@router.get("/documents", response_model=list[DocumentInfo])
def list_documents() -> list[DocumentInfo]:
    with get_pool().connection() as conn:
        rows = conn.execute(
            """
            SELECT d.id, d.title, d.source, d.metadata, count(c.id)
            FROM documents d LEFT JOIN chunks c ON c.document_id = d.id
            GROUP BY d.id ORDER BY d.title
            """
        ).fetchall()
    return [
        DocumentInfo(
            id=doc_id,
            title=title,
            source=source,
            format=meta.get("format"),
            pages=meta.get("pages"),
            chunks=chunks,
            ingested_at=meta.get("ingested_at"),
        )
        for doc_id, title, source, meta, chunks in rows
    ]


@router.post("/documents", response_model=list[UploadResult])
def upload_documents(files: list[UploadFile]) -> list[UploadResult]:
    """Upload PDF, Markdown or text files. Each is saved to data/uploads/ and ingested right away
    (chunked and embedded); uploading a file with the same name again updates it."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    return [_save_and_ingest(file) for file in files]


@router.delete("/documents/{document_id}", status_code=204)
def delete_document(document_id: int) -> None:
    """Remove a document and its chunks. Uploaded files are deleted from disk too; files in
    data/corpus stay, so `python -m scripts.ingest` would add them back."""
    with get_pool().connection() as conn:
        row = conn.execute("DELETE FROM documents WHERE id = %s RETURNING source", (document_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="document not found")
    path = (PROJECT_ROOT / row[0]).resolve()
    if path.is_relative_to(UPLOAD_DIR.resolve()):
        path.unlink(missing_ok=True)


def _save_and_ingest(file: UploadFile) -> UploadResult:
    name = safe_filename(file.filename or "")
    if not name or Path(name).suffix.lower() not in LOADERS:
        supported = ", ".join(sorted(LOADERS))
        return UploadResult(filename=file.filename or "", status="failed", error=f"unsupported file type; use {supported}")

    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        return UploadResult(filename=name, status="failed", error="file larger than 20 MB")

    path = UPLOAD_DIR / name
    existed = path.exists()
    path.write_bytes(data)
    try:
        result = ingest_file(path)
    except Exception as e:
        if not existed:
            path.unlink(missing_ok=True)  # don't leave an unreadable new file behind
        return UploadResult(filename=name, status="failed", error=f"{type(e).__name__}: {e}")
    return UploadResult(filename=name, status=result.status, chunks=result.chunks)


def safe_filename(filename: str) -> str:
    """Keep only the base name and safe characters, so an upload can't be written outside
    UPLOAD_DIR (e.g. "../../app/config.py") or carry odd characters into paths."""
    name = Path(filename.replace("\\", "/")).name
    name = re.sub(r"[^A-Za-z0-9._ ()-]", "_", name).strip(" .")
    return name[:150]
