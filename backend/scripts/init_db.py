"""Create the pgvector extension and the documents/chunks tables.

Usage (from backend/):
    python -m scripts.init_db            # create if missing
    python -m scripts.init_db --reset    # drop and recreate (deletes all ingested data)
"""

import argparse

from app.db import get_pool, init_schema


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reset", action="store_true", help="drop and recreate tables (deletes all data)")
    args = parser.parse_args()

    init_schema(reset=args.reset)

    with get_pool().connection() as conn:
        version = conn.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector'").fetchone()[0]
        docs, chunks = conn.execute(
            "SELECT (SELECT count(*) FROM documents), (SELECT count(*) FROM chunks)"
        ).fetchone()

    print(f"Schema ready (pgvector {version}). documents: {docs}, chunks: {chunks}")


if __name__ == "__main__":
    main()
