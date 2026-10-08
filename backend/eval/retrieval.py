"""Evaluate retrieval: does search rank the labelled source sections near the top?

Only query embeddings are needed (no chat model), so this is cheap to run.

Usage (from backend/):  python -m eval.retrieval
"""

import json
from collections import defaultdict

from app.retrieval import search
from eval.dataset import load_dataset
from eval.metrics import first_relevant_rank, recall_at_k, retrieval_summary
from eval.report import RESULTS, write_report

MODES = ("vector", "keyword", "hybrid")
DEPTH = 10  # results fetched per query; metrics look at the top 1, 3, 5 and the first-hit rank


def main() -> None:
    questions = [q for q in load_dataset() if q.answerable]
    results: dict[str, dict] = {}
    per_question: dict[str, dict] = defaultdict(dict)

    for mode in MODES:
        ranks, recalls = [], []
        by_category: dict[str, list[float]] = defaultdict(list)
        for q in questions:
            ranked = [(c.source, c.headings) for c in search(q.question, k=DEPTH, mode=mode)]
            rank = first_relevant_rank(ranked, q.sources)
            ranks.append(rank)
            recalls.append(recall_at_k(ranked, q.sources, 5))
            by_category[q.category].append(1 / rank if rank else 0)
            per_question[q.id][mode] = rank
        results[mode] = {
            **retrieval_summary(ranks, recalls),
            "mrr_by_category": {c: sum(v) / len(v) for c, v in by_category.items()},
        }

    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "retrieval.json").write_text(
        json.dumps({"questions": len(questions), "depth": DEPTH, "modes": results, "ranks": per_question}, indent=2)
    )

    print(f"Retrieval on {len(questions)} answerable questions (first relevant result within top {DEPTH})\n")
    print(f"{'mode':<9}{'hit@1':>8}{'hit@3':>8}{'hit@5':>8}{'recall@5':>10}{'MRR':>8}")
    for mode, m in results.items():
        print(f"{mode:<9}{m['hit@1']:>8.2f}{m['hit@3']:>8.2f}{m['hit@5']:>8.2f}{m['recall@5']:>10.2f}{m['mrr']:>8.3f}")
    misses = [qid for qid, r in per_question.items() if not r["hybrid"] or r["hybrid"] > 5]
    if misses:
        print(f"\nHybrid misses (no relevant chunk in top 5): {', '.join(misses)}")
    print(f"\nReport: {write_report()}")


if __name__ == "__main__":
    main()
