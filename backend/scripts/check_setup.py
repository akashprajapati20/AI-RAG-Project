"""Smoke test: can we reach Postgres/pgvector and the Gemini API?

Usage (from backend/):  python -m scripts.check_setup
"""

import sys

from google.genai import types

from app.config import get_settings
from app.db import get_pool, init_schema
from app.gemini import get_client


def check_database() -> bool:
    try:
        init_schema()
        with get_pool().connection() as conn:
            # Round-trip a vector to prove the pgvector type adapter works.
            distance = conn.execute("SELECT '[1,0,0]'::vector <=> '[0,1,0]'::vector").fetchone()[0]
        print(f"  ✓ Postgres + pgvector reachable (cosine distance of orthogonal vectors = {distance})")
        return True
    except Exception as e:
        print(f"  ✗ Database: {e}")
        print("    Is the container running?  docker compose up -d")
        return False


def check_gemini() -> bool:
    settings = get_settings()
    try:
        client = get_client()
    except RuntimeError as e:
        print(f"  ✗ Gemini: {e}")
        return False

    ok = True
    try:
        result = client.models.embed_content(
            model=settings.embedding_model,
            contents="What is retrieval-augmented generation?",
            config=types.EmbedContentConfig(
                task_type="RETRIEVAL_QUERY",
                output_dimensionality=settings.embedding_dim,
            ),
        )
        dim = len(result.embeddings[0].values)
        assert dim == settings.embedding_dim, f"expected {settings.embedding_dim} dims, got {dim}"
        print(f"  ✓ Embeddings: {settings.embedding_model} -> {dim} dims")
    except Exception as e:
        print(f"  ✗ Embeddings ({settings.embedding_model}): {e}")
        ok = False

    try:
        reply = client.models.generate_content(
            model=settings.chat_model,
            contents="Reply with exactly: OK",
            config=types.GenerateContentConfig(
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            ),
        )
        print(f"  ✓ Chat: {settings.chat_model} replied {reply.text.strip()!r}")
    except Exception as e:
        print(f"  ✗ Chat ({settings.chat_model}): {e}")
        _print_available_models(client)
        ok = False

    return ok


def _print_available_models(client) -> None:
    try:
        names = [
            m.name.removeprefix("models/")
            for m in client.models.list()
            if "generateContent" in (m.supported_actions or []) and "flash" in m.name
        ]
        print("    Flash models available to your key (set CHAT_MODEL in .env):")
        for name in sorted(names):
            print(f"      - {name}")
    except Exception:
        pass


def main() -> None:
    print("Database")
    db_ok = check_database()
    print("Gemini")
    gemini_ok = check_gemini()
    print("\nAll checks passed." if db_ok and gemini_ok else "\nFix the ✗ items above.")
    sys.exit(0 if db_ok and gemini_ok else 1)


if __name__ == "__main__":
    main()
