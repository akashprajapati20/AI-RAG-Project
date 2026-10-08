"""Write eval/REPORT.md from saved results. Makes no API calls, so it can be re-run any time.

Usage (from backend/):  python -m eval.report
"""

import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from eval.dataset import CATEGORIES, load_dataset
from eval.metrics import accuracy_by_category, answer_summary, is_hallucination

EVAL_DIR = Path(__file__).parent
RESULTS = EVAL_DIR / "results"
ANSWERS = RESULTS / "answers"
REPORT = EVAL_DIR / "REPORT.md"
SYSTEM_ORDER = ("closed_book", "plain_rag", "agent")


def write_report() -> Path:
    questions = load_dataset()
    lines = [
        "# Evaluation report",
        "",
        f"_Generated {datetime.now():%Y-%m-%d %H:%M} by `python -m eval.report` from `eval/results/`._",
        "",
        "## Test set",
        "",
        f"{len(questions)} questions about the Brindlewave corpus, written with reference answers, key facts and "
        "labelled source sections (`eval/dataset.jsonl`).",
        "",
        "| Category | Questions | What it tests |",
        "|---|---|---|",
    ]
    counts = Counter(q.category for q in questions)
    descriptions = {
        "fact": "one fact, stated plainly",
        "paraphrase": "different wording from the document (\"vacation\" vs \"paid time off\")",
        "identifier": "an exact token (INC-2026-031, TT-200C, insufficient_scope)",
        "table": "an answer inside a PDF table",
        "superseded": "a newer memo overrides the handbook",
        "multi_hop": "facts from two places",
        "arithmetic": "a calculation on document numbers",
        "date_math": "a day count between document dates",
        "unanswerable": "not documented: the right answer is to refuse",
    }
    lines += [f"| {c} | {counts[c]} | {descriptions[c]} |" for c in CATEGORIES if counts[c]]

    retrieval_path = RESULTS / "retrieval.json"
    if retrieval_path.exists():
        lines += _retrieval_section(json.loads(retrieval_path.read_text()))

    records = {s: _read(ANSWERS / f"{s}.jsonl") for s in SYSTEM_ORDER}
    records = {s: r for s, r in records.items() if r}
    if records:
        meta = json.loads((ANSWERS / "meta.json").read_text())
        lines += _answers_section(records, meta)

    lines += [
        "",
        "## Caveats",
        "",
        "- **Small test set** (one run, ~40 questions): differences of a few points are within noise.",
        "- **LLM-as-judge**: correctness and unsupported claims are graded by a Gemini model, which can be wrong "
        "and may favour answers from its own model family. The deterministic key-fact check is a cross-check.",
        "- **Free-tier models**: answers here come from the model listed under *Answer quality*; the production "
        "default (`CHAT_MODEL`) may score differently.",
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return REPORT


def _retrieval_section(data: dict) -> list[str]:
    modes = data["modes"]
    lines = [
        "",
        "## Retrieval",
        "",
        f"Each answerable question ({data['questions']}) is searched with every mode; a result is relevant if it "
        "comes from a labelled document section. **Hit@k**: a relevant result in the top k. **Recall@5**: share "
        "of all labelled sections in the top 5. **MRR**: mean of 1/rank of the first relevant result.",
        "",
        "| Mode | Hit@1 | Hit@3 | Hit@5 | Recall@5 | MRR |",
        "|---|---|---|---|---|---|",
    ]
    for mode, m in modes.items():
        lines.append(f"| {mode} | {m['hit@1']:.0%} | {m['hit@3']:.0%} | {m['hit@5']:.0%} | {m['recall@5']:.0%} | {m['mrr']:.3f} |")
    categories = [c for c in CATEGORIES if c in next(iter(modes.values()))["mrr_by_category"]]
    lines += ["", "MRR by category:", "", "| Category | " + " | ".join(modes) + " |", "|---|" + "---|" * len(modes)]
    for c in categories:
        lines.append(f"| {c} | " + " | ".join(f"{m['mrr_by_category'][c]:.2f}" for m in modes.values()) + " |")
    return lines


def _answers_section(records: dict[str, list[dict]], meta: dict) -> list[str]:
    summaries = {s: answer_summary(r) for s, r in records.items()}
    systems = list(records)
    lines = [
        "",
        "## Answer quality",
        "",
        f"Answer model **{meta['answer_model']}** for every system; judge **{meta['judge_model']}**; the agent's "
        f"router/grader/rewriter use **{meta['fast_model']}**.",
        "",
        "- **closed_book**: the model alone, no documents.",
        "- **plain_rag**: one hybrid search (top 6) + one answer call with the same grounding and citation rules.",
        "- **agent**: routing, LLM relevance grading, one query rewrite, tools, deterministic refusal.",
        "",
        "| Metric | " + " | ".join(systems) + " |",
        "|---|" + "---|" * len(systems),
    ]
    rows = [
        ("questions", "Questions answered", "{:.0f}"),
        ("accuracy", "Accuracy (answerable; partial = ½)", "{:.0%}"),
        ("key_fact_recall", "Key facts present (deterministic)", "{:.0%}"),
        ("hallucination_rate", "**Hallucination rate** (any unsupported claim)", "{:.0%}"),
        ("refusal_accuracy", "Refused unanswerable questions", "{:.0%}"),
        ("false_refusal_rate", "Refused answerable questions", "{:.0%}"),
        ("citation_rate", "Answers with ≥1 citation", "{:.0%}"),
        ("citation_precision", "Citations pointing to a labelled document", "{:.0%}"),
        ("avg_latency_s", "Avg latency (s)", "{:.1f}"),
        ("avg_llm_calls", "Avg LLM calls per question", "{:.1f}"),
        ("avg_tokens", "Avg tokens per question", "{:,.0f}"),
    ]
    for key, label, fmt in rows:
        cells = [fmt.format(summaries[s][key]) if summaries[s][key] is not None else "–" for s in systems]
        lines.append(f"| {label} | " + " | ".join(cells) + " |")

    by_category = {s: accuracy_by_category(r) for s, r in records.items()}
    counts = Counter(r["category"] for r in next(iter(records.values())))
    lines += [
        "",
        "### By category",
        "",
        "Accuracy per category (for *unanswerable*: share correctly refused).",
        "",
        "| Category | n | " + " | ".join(systems) + " |",
        "|---|---|" + "---|" * len(systems),
    ]
    for c in CATEGORIES:
        if counts[c]:
            cells = [f"{by_category[s][c]:.0%}" if c in by_category[s] else "–" for s in systems]
            lines.append(f"| {c} | {counts[c]} | " + " | ".join(cells) + " |")

    for system in ("agent", "plain_rag"):
        failures = [r for r in records.get(system, []) if r["verdict"] in ("incorrect", "partially_correct") or is_hallucination(r)]
        if not failures:
            continue
        lines += ["", f"### {system}: wrong, partial or unsupported answers ({len(failures)})", ""]
        for r in failures:
            answer = " ".join(r["answer"].split())
            lines.append(f"- **{r['id']}** ({r['category']}) — *{r['verdict']}*: {r['question']}")
            lines.append(f"  - Answer: {answer[:300]}{'…' if len(answer) > 300 else ''}")
            if r["unsupported_claims"]:
                lines.append("  - Unsupported: " + "; ".join(r["unsupported_claims"]))
            lines.append(f"  - Judge: {r['explanation']}")
    return lines


def _read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


if __name__ == "__main__":
    print(write_report())
