"""Ingest documents into Postgres/pgvector.

Usage (from backend/):
    python -m scripts.ingest                       # ingest data/corpus (skips unchanged files)
    python -m scripts.ingest path/to/folder        # ingest another folder
    python -m scripts.ingest --force               # re-embed everything
    python -m scripts.ingest --prune               # also delete documents whose files are gone
    python -m scripts.ingest --dry-run             # load + chunk only: no API calls, no DB writes
    python -m scripts.ingest --dry-run --show-chunks
"""

import argparse
import time
from pathlib import Path

from app.config import PROJECT_ROOT
from app.db import get_pool, init_schema
from app.ingest import ingest_directory, prepare, prune, source_id
from app.loaders import LOADERS


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path", nargs="?", type=Path, default=PROJECT_ROOT / "data" / "corpus")
    parser.add_argument("--force", action="store_true", help="re-process files even if unchanged")
    parser.add_argument("--prune", action="store_true", help="delete documents whose files no longer exist")
    parser.add_argument("--dry-run", action="store_true", help="load and chunk only; no API calls or DB writes")
    parser.add_argument("--show-chunks", action="store_true", help="with --dry-run, print every chunk")
    args = parser.parse_args()

    directory = args.path.resolve()
    if not directory.is_dir():
        raise SystemExit(f"Not a directory: {directory}")

    if args.dry_run:
        dry_run(directory, args.show_chunks)
        return

    init_schema()
    started = time.perf_counter()
    results = ingest_directory(directory, force=args.force)

    width = max((len(r.source) for r in results), default=0)
    for r in results:
        detail = f"{r.chunks} chunks" if r.chunks else (r.error or "")
        print(f"  {r.status:<9}  {r.source:<{width}}  {detail}")

    if args.prune:
        for source in prune(directory, keep={r.source for r in results}):
            print(f"  {'removed':<9}  {source}")

    counts = {s: sum(r.status == s for r in results) for s in ("added", "updated", "unchanged", "failed")}
    with get_pool().connection() as conn:
        docs, chunks = conn.execute("SELECT (SELECT count(*) FROM documents), (SELECT count(*) FROM chunks)").fetchone()
    print(
        f"\nDone in {time.perf_counter() - started:.1f}s: "
        + ", ".join(f"{n} {s}" for s, n in counts.items())
        + f". Database holds {docs} documents / {chunks} chunks."
    )


def dry_run(directory: Path, show_chunks: bool) -> None:
    files = sorted(p for p in directory.rglob("*") if p.is_file() and p.suffix.lower() in LOADERS)
    total = 0
    for path in files:
        doc, chunks = prepare(path)
        total += len(chunks)
        sizes = [len(c.text) for c in chunks] or [0]
        print(
            f"{source_id(path)}  |  {doc.title!r}  |  {len(doc.sections)} sections -> {len(chunks)} chunks "
            f"(chars min/avg/max {min(sizes)}/{sum(sizes) // len(sizes)}/{max(sizes)})"
        )
        if show_chunks:
            for i, chunk in enumerate(chunks):
                pages = f" pages {chunk.pages}" if chunk.pages else ""
                print(f"\n  ── chunk {i}{pages} ──\n" + "\n".join("  │ " + line for line in chunk.text.splitlines()))
            print()
    print(f"\n{len(files)} files -> {total} chunks (dry run: nothing embedded or stored)")


if __name__ == "__main__":
    main()
