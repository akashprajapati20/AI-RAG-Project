import pytest

from eval.dataset import CATEGORIES, ExpectedSource, load_dataset
from eval.metrics import (
    accuracy_by_category,
    answer_summary,
    first_relevant_rank,
    is_hallucination,
    key_fact_recall,
    recall_at_k,
)

HANDBOOK = ExpectedSource("employee_handbook", "Paid time off")
MEMO = ExpectedSource("hr_policy_update", "")


def test_dataset_is_valid_and_covers_every_category():
    questions = load_dataset()
    assert len(questions) >= 40
    assert {q.category for q in questions} == set(CATEGORIES)


def test_expected_source_matching():
    assert HANDBOOK.matches("data/corpus/employee_handbook.pdf", ["2. Paid time off (PTO)", "3. Sick leave"])
    assert not HANDBOOK.matches("data/corpus/employee_handbook.pdf", ["7. Expenses and travel"])
    assert MEMO.matches("data/corpus/hr_policy_update_2026.pdf", [])  # "" heading = any chunk of the document


def test_rank_and_recall():
    ranked = [("data/corpus/faq.md", ["Billing"]), ("data/corpus/hr_policy_update_2026.pdf", []),
              ("data/corpus/employee_handbook.pdf", ["2. Paid time off (PTO)"])]
    assert first_relevant_rank(ranked, (HANDBOOK, MEMO)) == 2
    assert first_relevant_rank(ranked[:1], (HANDBOOK,)) is None
    assert recall_at_k(ranked, (HANDBOOK, MEMO), k=2) == 0.5
    assert recall_at_k(ranked, (HANDBOOK, MEMO), k=3) == 1.0


@pytest.mark.parametrize(
    "answer, facts, expected",
    [
        ("It costs €58,190.40 per year.", ("58190.4",), 1.0),
        ("You can carry over up to 8 days.", ("8",), 1.0),
        ("Founded in 2018.", ("8",), 0.0),  # a whole number must match as a whole number
        ("Uptime is 99.9%.", ("99",), 0.0),
        ("Introduced in release 4.2.0.", ("4.2",), 1.0),
        ("From −35 °C to +10 °C", ("35", "10"), 1.0),
        ("Marcus Lindqvist", ("lindqvist", "Rotterdam"), 0.5),
        ("anything", (), 1.0),
    ],
)
def test_key_fact_recall(answer, facts, expected):
    assert key_fact_recall(answer, facts) == expected


def record(**overrides):
    base = {"category": "fact", "answerable": True, "verdict": "correct", "unsupported_claims": [],
            "key_fact_recall": 1.0, "citations": [], "latency_s": 1.0, "llm_calls": 1,
            "input_tokens": 10, "output_tokens": 5}
    return {**base, **overrides}


def test_hallucination_rules():
    assert not is_hallucination(record())
    assert is_hallucination(record(unsupported_claims=["made-up price"]))
    assert is_hallucination(record(answerable=False, verdict="incorrect"))  # answered the unanswerable
    assert not is_hallucination(record(answerable=False, verdict="refused"))
    # "Not in the documents" matches the reference answer, so the judge may call a decline "correct".
    assert not is_hallucination(record(answerable=False, verdict="correct"))


def test_answer_summary_and_categories():
    records = [
        record(verdict="correct", citations=[{"relevant": True}]),
        record(verdict="partially_correct", citations=[{"relevant": False}], unsupported_claims=["x"]),
        record(category="unanswerable", answerable=False, verdict="refused"),
        record(category="unanswerable", answerable=False, verdict="correct"),
        record(category="unanswerable", answerable=False, verdict="incorrect"),
    ]
    summary = answer_summary(records)
    assert summary["accuracy"] == 0.75
    assert summary["hallucination_rate"] == 2 / 5  # the unsupported claim + the answered unanswerable
    assert summary["refusal_accuracy"] == 2 / 3
    assert summary["citation_precision"] == 0.5
    assert accuracy_by_category(records) == {"fact": 0.75, "unanswerable": 2 / 3}


def test_every_labelled_source_exists_in_the_database():
    """A typo in a label would silently count every retrieval as a miss."""
    from app.db import get_pool, init_schema

    try:
        init_schema()
        with get_pool().connection() as conn:
            chunks = [(s, m.get("headings", [])) for s, m in conn.execute(
                "SELECT d.source, c.metadata FROM chunks c JOIN documents d ON d.id = c.document_id")]
    except Exception as e:
        pytest.skip(f"database unavailable: {e}")
    if not chunks:
        pytest.skip("no chunks; run `python -m scripts.ingest` first")
    missing = [(q.id, e) for q in load_dataset() for e in q.sources if not any(e.matches(s, h) for s, h in chunks)]
    assert missing == []
