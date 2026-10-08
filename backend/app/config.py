"""Central configuration, loaded from environment variables or the project-root .env file."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", extra="ignore")

    # Gemini
    google_api_key: str = ""
    chat_model: str = "gemini-3.5-flash"  # writes the answers
    fast_model: str = "gemini-3.5-flash-lite"  # quick decisions: routing, grading, query rewrites
    embedding_model: str = "gemini-embedding-001"
    # gemini-embedding-001 returns 3072 dims by default. We ask for 768 instead:
    # pgvector's HNSW index supports at most 2000 dims, and 768 loses very little quality.
    embedding_dim: int = 768

    # Agent. Gemini 3 "thinking" before answering: "minimal" was ~1.4s per call in our test;
    # "low"/default were 5-20x slower and far more variable under load.
    thinking_level: str = "minimal"
    # Requests per minute per chat model; 0 = no limit. Free-tier keys have low per-minute
    # limits, so the evaluation sets this to pace its many calls.
    llm_requests_per_minute: float = 0

    # Chunking. Changing these makes the next ingest run re-process every document.
    chunk_size: int = 1200  # characters, roughly 300 tokens
    chunk_overlap: int = 150  # characters repeated between pieces of a long section

    # Postgres (see docker-compose.yml)
    database_url: str = "postgresql://rag:rag@localhost:5432/rag"

    # API: browser origins allowed to call it (the React dev server in Part 6)
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
