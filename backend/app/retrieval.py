"""Hybrid retrieval: vector similarity (pgvector) + keyword search (Postgres full-text),
merged with Reciprocal Rank Fusion (RRF).

Why both? They fail differently:
  - vector search understands meaning ("vacation" finds "paid time off") but blurs exact
    tokens such as "INC-2026-031", "TT-200C" or "insufficient_scope";
  - keyword search nails exact tokens but misses synonyms and paraphrases.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Literal

from app.db import get_pool
from app.embeddings import embed_query

Mode = Literal["hybrid", "vector", "keyword"]

# Results each retriever contributes before fusion. Keep this well below the corpus size: RRF
# rewards appearing in *both* lists, so if each list covers half the corpus, weak keyword matches
# (e.g. on "data") that also sit low in the vector list outrank a strong vector-only hit.
# On our 39-chunk corpus, 20 caused exactly that miss; 10 fixed it with no other losses.
CANDIDATES = 10
RRF_K = 60  # standard RRF constant; stops the very top ranks from dominating the fused score


@dataclass
class RetrievedChunk:
    chunk_id: int
    document_id: int
    title: str
    source: str
    content: str
    headings: list[str]
    pages: list[int]
    score: float  # fused RRF score: only meaningful for ordering
    similarity: float | None = None  # cosine similarity to the query (not computed in keyword mode)
    ranks: dict[str, int] = field(default_factory=dict)  # rank per retriever, e.g. {"vector": 3, "keyword": 1}

    @property
    def citation(self) -> str:
        """e.g. "Tally Pricing and Plans 2026 › 4. SLA credits; 5. Free trial (pp. 1–2)"."""
        text = self.title
        if self.headings:
            text += " › " + "; ".join(self.headings[:2]) + (" …" if len(self.headings) > 2 else "")
        if self.pages:
            first, last = self.pages[0], self.pages[-1]
            text += f" (p. {first})" if first == last else f" (pp. {first}–{last})"
        return text


def search(query: str, k: int = 5, mode: Mode = "hybrid", candidates: int = CANDIDATES) -> list[RetrievedChunk]:
    """Return the k chunks most relevant to a natural-language query."""
    vector = _query_vector(query) if mode in ("vector", "hybrid") else None
    limit = max(candidates, k)

    with get_pool().connection() as conn:
        rankings: dict[str, list[int]] = {}
        if vector is not None:
            rankings["vector"] = [r[0] for r in conn.execute(_VECTOR_SQL, {"vector": vector, "limit": limit})]
        if mode in ("keyword", "hybrid"):
            rankings["keyword"] = [r[0] for r in conn.execute(_KEYWORD_SQL, {"query": query, "limit": limit})]

        fused = reciprocal_rank_fusion(rankings)[:k]
        rows = conn.execute(_FETCH_SQL, {"ids": [chunk_id for chunk_id, _, _ in fused], "vector": vector})
        by_id = {row[0]: row for row in rows}

    results = []
    for chunk_id, score, ranks in fused:
        _, document_id, title, source, content, metadata, similarity = by_id[chunk_id]
        results.append(
            RetrievedChunk(
                chunk_id=chunk_id,
                document_id=document_id,
                title=title,
                source=source,
                content=content,
                headings=metadata.get("headings", []),
                pages=metadata.get("pages", []),
                score=score,
                similarity=similarity,
                ranks=ranks,
            )
        )
    return results


def reciprocal_rank_fusion(
    rankings: dict[str, list[int]], k: int = RRF_K
) -> list[tuple[int, float, dict[str, int]]]:
    """Merge ranked id lists: score(id) = sum over lists of 1 / (k + rank).

    Uses only positions, so cosine similarities and ts_rank scores (different, incomparable
    scales) never need to be normalised. An item ranked well by both retrievers beats one
    ranked first by only one. Returns (id, score, {retriever: rank}) sorted by score.
    """
    scores: dict[int, float] = defaultdict(float)
    ranks: dict[int, dict[str, int]] = defaultdict(dict)
    for name, ids in rankings.items():
        for rank, item in enumerate(ids, start=1):
            scores[item] += 1 / (k + rank)
            ranks[item][name] = rank
    ordered = sorted(scores, key=scores.__getitem__, reverse=True)
    return [(item, scores[item], ranks[item]) for item in ordered]


@lru_cache(maxsize=1024)
def _query_vector(query: str):
    """Cached, so the agent and the eval harness don't pay for re-embedding repeated queries."""
    return embed_query(query)


# <=> is pgvector's cosine-distance operator; ORDER BY ... LIMIT on it uses the HNSW index.
_VECTOR_SQL = """
    SELECT id FROM chunks
    ORDER BY embedding <=> %(vector)s
    LIMIT %(limit)s
"""

# plainto_tsquery ANDs every word ('caus' & 'march' & 'outag'), which is too strict for
# questions. Switch to OR, and let ts_rank favour chunks that match more of the words.
# numnode() = 0 means the query was only stop words ("what is it"): return nothing.
_KEYWORD_SQL = """
    WITH q AS (SELECT replace(plainto_tsquery('english', %(query)s)::text, ' & ', ' | ')::tsquery AS tsq)
    SELECT c.id FROM chunks c, q
    WHERE numnode(q.tsq) > 0 AND c.tsv @@ q.tsq
    ORDER BY ts_rank(c.tsv, q.tsq) DESC, c.id
    LIMIT %(limit)s
"""

_FETCH_SQL = """
    SELECT c.id, c.document_id, d.title, d.source, c.content, c.metadata,
           1 - (c.embedding <=> %(vector)s) AS similarity
    FROM chunks c JOIN documents d ON d.id = c.document_id
    WHERE c.id = ANY(%(ids)s)
"""
