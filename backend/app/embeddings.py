"""Gemini embeddings for document chunks and search queries."""

import numpy as np
from google.genai import types

from app.config import get_settings
from app.gemini import get_client

BATCH_SIZE = 100  # max texts per embed_content request


def embed_documents(texts: list[str]) -> list[np.ndarray]:
    """Embed texts that will be stored and searched over."""
    return _embed(texts, task_type="RETRIEVAL_DOCUMENT")


def embed_query(text: str) -> np.ndarray:
    """Embed a search query. Gemini embeds queries and documents slightly differently
    (asymmetric retrieval), which improves how well questions match passages."""
    return _embed([text], task_type="RETRIEVAL_QUERY")[0]


def _embed(texts: list[str], task_type: str) -> list[np.ndarray]:
    settings = get_settings()
    config = types.EmbedContentConfig(task_type=task_type, output_dimensionality=settings.embedding_dim)
    vectors: list[np.ndarray] = []
    for start in range(0, len(texts), BATCH_SIZE):
        result = get_client().models.embed_content(
            model=settings.embedding_model,
            contents=texts[start : start + BATCH_SIZE],
            config=config,
        )
        for embedding in result.embeddings:
            vector = np.asarray(embedding.values, dtype=np.float32)
            # Shortened (non-3072) Gemini embeddings aren't unit length; normalise so cosine
            # similarity and dot product give the same ranking.
            vectors.append(vector / np.linalg.norm(vector))
    return vectors
