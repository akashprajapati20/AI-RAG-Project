"""The FastAPI app.

Run (from backend/):  ../.venv/bin/uvicorn app.api.main:app --reload --port 8000
Interactive docs:     http://localhost:8000/docs
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.agent.graph import build_graph
from app.api import chat, documents
from app.config import get_settings
from app.db import get_pool, init_schema
from app.memory import get_checkpointer


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: make sure the tables exist, then build one agent that remembers conversations
    # in Postgres. Every request shares it; per-conversation state lives in the checkpointer.
    init_schema()
    app.state.checkpointer = get_checkpointer()
    app.state.graph = build_graph(checkpointer=app.state.checkpointer)
    yield
    # Connection pools close at interpreter exit (see app.db / app.memory).


app = FastAPI(
    title="Agentic RAG Assistant",
    description="Ask questions about Brindlewave's internal documents; answers cite their sources.",
    version="0.5.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(chat.router)
app.include_router(documents.router)


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse("/docs")


@app.get("/health", tags=["health"])
def health() -> dict:
    settings = get_settings()
    with get_pool().connection() as conn:
        documents_count, chunks_count = conn.execute(
            "SELECT (SELECT count(*) FROM documents), (SELECT count(*) FROM chunks)"
        ).fetchone()
    return {
        "status": "ok",
        "documents": documents_count,
        "chunks": chunks_count,
        "models": {"chat": settings.chat_model, "fast": settings.fast_model, "embedding": settings.embedding_model},
    }
