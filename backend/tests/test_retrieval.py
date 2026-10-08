import pytest

from app.retrieval import RetrievedChunk, reciprocal_rank_fusion, search

# ---------------------------------------------------------------- unit tests (no services)


def test_rrf_rewards_agreement_between_retrievers():
    fused = reciprocal_rank_fusion({"vector": [1, 2, 3], "keyword": [4, 2, 5]})
    ids = [item for item, _, _ in fused]
    assert ids[0] == 2  # ranked 2nd by both beats ranked 1st by only one
    assert dict((item, ranks) for item, _, ranks in fused)[2] == {"vector": 2, "keyword": 2}


def test_rrf_single_list_keeps_its_order():
    fused = reciprocal_rank_fusion({"vector": [7, 3, 9]})
    assert [item for item, _, _ in fused] == [7, 3, 9]


def make_chunk(headings, pages):
    return RetrievedChunk(1, 1, "Doc", "data/corpus/doc.pdf", "text", headings, pages, score=0.0)


def test_citation_formats_headings_and_pages():
    assert make_chunk(["4. SLA credits"], [1]).citation == "Doc › 4. SLA credits (p. 1)"
    assert make_chunk(["A", "B"], [1, 2]).citation == "Doc › A; B (pp. 1–2)"
    assert make_chunk(["A", "B", "C"], []).citation == "Doc › A; B …"
    assert make_chunk([], []).citation == "Doc"


# ---------------------------------------------------------------- live tests (Postgres + Gemini)


@pytest.fixture(scope="module")
def live():
    """Skip unless the database is up, the corpus is ingested and a Gemini key is configured."""
    from app.config import get_settings
    from app.db import get_pool, init_schema

    if not get_settings().google_api_key:
        pytest.skip("GOOGLE_API_KEY not set")
    try:
        init_schema()
        with get_pool().connection() as conn:
            chunks = conn.execute("SELECT count(*) FROM chunks").fetchone()[0]
    except Exception as e:
        pytest.skip(f"database unavailable: {e}")
    if not chunks:
        pytest.skip("no chunks; run `python -m scripts.ingest` first")


def top_sources(query, mode="hybrid", k=3):
    return [c.source for c in search(query, k=k, mode=mode)]


def test_keyword_search_matches_identifier_in_document_title(live):
    # "INC-2026-031" appears in the postmortem only in its title (the onboarding guide also
    # mentions it once), so this fails if titles aren't in the keyword index.
    assert any("postmortem" in s for s in top_sources("INC-2026-031", mode="keyword", k=5))


def test_hybrid_ranks_document_named_by_identifier_first(live):
    assert "postmortem" in top_sources("INC-2026-031", k=1)[0]


def test_vector_search_understands_synonyms(live):
    # The corpus never says "vacation"; it says "paid time off".
    assert "employee_handbook" in top_sources("How much vacation do I get?", mode="vector", k=1)[0]


def test_hybrid_surfaces_both_the_old_and_the_new_policy(live):
    sources = top_sources("How many PTO days can I carry over?")
    assert any("employee_handbook" in s for s in sources)
    assert any("hr_policy_update" in s for s in sources)


def test_results_are_ordered_and_limited(live):
    results = search("battery life of a tag", k=4)
    assert len(results) == 4
    assert [r.score for r in results] == sorted((r.score for r in results), reverse=True)
    assert all(r.similarity is not None for r in results)


def test_stop_word_only_query_returns_no_keyword_results(live):
    assert search("what is it", mode="keyword") == []
