"""Metric functions. Pure Python, so they're unit-tested without any API calls."""

import re
from collections import defaultdict
from statistics import mean

from eval.dataset import ExpectedSource

# ---------------------------------------------------------------- retrieval

Ranked = list[tuple[str, list[str]]]  # search results as (document source, chunk headings)


def first_relevant_rank(results: Ranked, expected: tuple[ExpectedSource, ...]) -> int | None:
    """1-based rank of the first result matching any expected source; None if none does."""
    for rank, (source, headings) in enumerate(results, start=1):
        if any(e.matches(source, headings) for e in expected):
            return rank
    return None


def recall_at_k(results: Ranked, expected: tuple[ExpectedSource, ...], k: int) -> float:
    """Share of the labelled sections that appear in the top k. Hit@k asks "is anything relevant
    there?"; recall asks "is everything there?", which matters for multi-hop questions."""
    top = results[:k]
    return sum(any(e.matches(source, headings) for source, headings in top) for e in expected) / len(expected)


def retrieval_summary(ranks: list[int | None], recalls: list[float]) -> dict:
    return {
        "hit@1": mean(r is not None and r <= 1 for r in ranks),
        "hit@3": mean(r is not None and r <= 3 for r in ranks),
        "hit@5": mean(r is not None and r <= 5 for r in ranks),
        "recall@5": mean(recalls),
        "mrr": mean(1 / r if r else 0 for r in ranks),
    }


# ---------------------------------------------------------------- answers


def normalize(text: str) -> str:
    """Lower-case, unify minus signs and spaces, and drop thousands separators, so that
    "€58,190.40" contains "58190.4" and "−35 °C" contains "-35"."""
    text = text.lower().replace("−", "-").replace("–", "-")
    text = re.sub(r"[  ]", " ", text)
    return re.sub(r"(?<=\d)[, ](?=\d{3}\b)", "", text)


def key_fact_recall(answer: str, facts: tuple[str, ...]) -> float:
    """Share of key facts present in the answer. Whole numbers must match as whole numbers
    ("8" is not found in "2018" or "8.5"); everything else is a substring check."""
    if not facts:
        return 1.0
    text = normalize(answer)
    found = 0
    for fact in facts:
        fact = normalize(fact)
        if fact.isdigit():
            found += bool(re.search(rf"(?<![\d.,]){fact}(?![\d]|[.,]\d)", text))
        else:
            found += fact in text
    return found / len(facts)


VERDICT_SCORE = {"correct": 1.0, "partially_correct": 0.5, "incorrect": 0.0, "refused": 0.0}


def declined(record: dict) -> bool:
    """For an unanswerable question: did the system say the documents don't cover it? The judge
    labels that "refused" or "correct" (it matches the reference, "Not in the documents")."""
    return record["verdict"] in ("refused", "correct")


def is_hallucination(record: dict) -> bool:
    """An answer that states something its evidence doesn't support. For an unanswerable
    question, answering instead of declining counts too: anything said is invented."""
    if not record["answerable"]:
        return not declined(record) or bool(record["unsupported_claims"])
    return record["verdict"] != "refused" and bool(record["unsupported_claims"])


def answer_summary(records: list[dict]) -> dict:
    answerable = [r for r in records if r["answerable"]]
    unanswerable = [r for r in records if not r["answerable"]]
    cited = [c for r in answerable for c in r["citations"]]
    return {
        "questions": len(records),
        "accuracy": _mean(VERDICT_SCORE[r["verdict"]] for r in answerable),
        "key_fact_recall": _mean(r["key_fact_recall"] for r in answerable),
        "hallucination_rate": _mean(is_hallucination(r) for r in records),
        "refusal_accuracy": _mean(declined(r) for r in unanswerable),
        "false_refusal_rate": _mean(r["verdict"] == "refused" for r in answerable),
        # Citation metrics only make sense for systems that cite (not closed-book).
        "citation_rate": _mean(bool(r["citations"]) for r in answerable) if cited else None,
        "citation_precision": _mean(c["relevant"] for c in cited) if cited else None,
        "avg_latency_s": _mean(r["latency_s"] for r in records),
        "avg_llm_calls": _mean(r["llm_calls"] for r in records),
        "avg_tokens": _mean(r["input_tokens"] + r["output_tokens"] for r in records),
    }


def accuracy_by_category(records: list[dict]) -> dict[str, float]:
    """Accuracy per category; for unanswerable questions, the share correctly refused."""
    groups: dict[str, list[float]] = defaultdict(list)
    for r in records:
        score = declined(r) if not r["answerable"] else VERDICT_SCORE[r["verdict"]]
        groups[r["category"]].append(float(score))
    return {category: mean(scores) for category, scores in groups.items()}


def _mean(values) -> float | None:
    values = list(values)
    return mean(values) if values else None
