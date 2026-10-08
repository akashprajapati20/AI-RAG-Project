"""Evaluate answers: closed-book vs plain RAG vs the agent, graded by an LLM judge.

Results are saved after every question, and a re-run skips what's already done, so a run that
stops (e.g. a Gemini quota running out) continues where it left off.

Usage (from backend/):
    python -m eval.answers                                   # everything (resumes)
    python -m eval.answers --systems agent --limit 5         # a quick check
    python -m eval.answers --categories superseded multi_hop
    python -m eval.answers --fresh                           # discard saved results first
    python -m eval.answers --answer-model gemini-3.5-flash   # evaluate the production answer model

Defaults suit a free-tier key: gemini-3.5-flash allows only ~20 requests/day, so answers and
grading use FAST_MODEL (gemini-3.5-flash-lite), paced to --rpm requests per minute per model.
"""

import argparse
import json
import shutil

from app.config import get_settings
from app.db import init_schema
from eval.dataset import CATEGORIES, Question, load_dataset
from eval.judge import Judgement, judge
from eval.metrics import answer_summary, is_hallucination, key_fact_recall
from eval.report import ANSWERS, write_report
from eval.systems import SYSTEMS, SystemOutput


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--systems", nargs="+", choices=list(SYSTEMS), default=list(SYSTEMS))
    parser.add_argument("--categories", nargs="+", choices=CATEGORIES)
    parser.add_argument("--ids", nargs="+", help="only these question ids")
    parser.add_argument("--limit", type=int, help="only the first N matching questions")
    parser.add_argument("--answer-model", default=settings.fast_model, help="model that writes answers (all systems)")
    parser.add_argument("--judge-model", default=settings.fast_model, help="model that grades answers")
    parser.add_argument("--rpm", type=float, default=12, help="max requests per minute per model (0 = no limit)")
    parser.add_argument("--fresh", action="store_true", help="delete saved answer results first")
    args = parser.parse_args()

    # Set before any model is created: every system (including the agent's generate step)
    # reads CHAT_MODEL from settings, and models are cached per name with this rate limit.
    settings.chat_model = args.answer_model
    settings.llm_requests_per_minute = args.rpm
    init_schema()

    questions = select(load_dataset(), args)
    if args.fresh and ANSWERS.exists():
        shutil.rmtree(ANSWERS)
    check_meta(args, settings)

    stopped = False
    for system in args.systems:
        path = ANSWERS / f"{system}.jsonl"
        done = {r["id"] for r in read_records(path)}
        todo = [q for q in questions if q.id not in done]
        print(f"\n== {system}: {len(todo)} to run, {len(questions) - len(todo)} already done")
        for i, q in enumerate(todo, start=1):
            try:
                output = SYSTEMS[system](q.question)
                judgement = judge(q, output, args.judge_model)
            except Exception as e:
                if "RESOURCE_EXHAUSTED" in str(e):
                    print(f"   Gemini quota used up at {system}/{q.id}. Progress is saved; run the same command later to resume.")
                    stopped = True
                    break
                print(f"   {q.id}: {type(e).__name__}: {str(e).splitlines()[0][:200]} (will retry on the next run)")
                continue
            record = make_record(q, output, judgement)
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
            flag = "  ⚠ hallucination" if is_hallucination(record) else ""
            print(f"   [{i}/{len(todo)}] {q.id:<28} {record['verdict']:<18} {output.latency_s:5.1f}s {output.llm_calls} calls{flag}")
        if stopped:
            break

    print_summary(args.systems)
    print(f"\nReport: {write_report()}")


def select(questions: list[Question], args) -> list[Question]:
    if args.categories:
        questions = [q for q in questions if q.category in args.categories]
    if args.ids:
        questions = [q for q in questions if q.id in args.ids]
    return questions[: args.limit] if args.limit else questions


def check_meta(args, settings) -> None:
    """Refuse to mix results from different models in one results folder."""
    meta = {"answer_model": args.answer_model, "judge_model": args.judge_model,
            "fast_model": settings.fast_model, "embedding_model": settings.embedding_model}
    path = ANSWERS / "meta.json"
    if path.exists():
        saved = json.loads(path.read_text())
        if saved != meta:
            raise SystemExit(f"Saved results used {saved}, not {meta}. Re-run with --fresh to start over.")
    ANSWERS.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(meta, indent=2))


def make_record(q: Question, output: SystemOutput, judgement: Judgement) -> dict:
    expected_documents = {e.source for e in q.sources}
    return {
        "id": q.id,
        "category": q.category,
        "answerable": q.answerable,
        "question": q.question,
        "answer": output.answer,
        "verdict": judgement.verdict,
        "unsupported_claims": judgement.unsupported_claims,
        "explanation": judgement.explanation,
        "key_fact_recall": key_fact_recall(output.answer, q.key_facts),
        # A citation is "relevant" if it points into one of the documents labelled for this question.
        "citations": [
            {"n": c["n"], "citation": c["citation"], "relevant": any(d in c["source"] for d in expected_documents)}
            for c in output.citations
        ],
        "sources_seen": len(output.sources),
        "tool_results": output.tool_results,
        "details": output.details,
        "latency_s": round(output.latency_s, 2),
        "llm_calls": output.llm_calls,
        "input_tokens": output.input_tokens,
        "output_tokens": output.output_tokens,
    }


def read_records(path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def print_summary(systems: list[str]) -> None:
    summaries = {s: answer_summary(r) for s in systems if (r := read_records(ANSWERS / f"{s}.jsonl"))}
    if not summaries:
        return
    rows = [
        ("questions", "questions", "{:.0f}"),
        ("accuracy", "accuracy", "{:.0%}"),
        ("key_fact_recall", "key facts", "{:.0%}"),
        ("hallucination_rate", "hallucinations", "{:.0%}"),
        ("refusal_accuracy", "refused unanswerable", "{:.0%}"),
        ("false_refusal_rate", "false refusals", "{:.0%}"),
        ("citation_precision", "citation precision", "{:.0%}"),
        ("avg_latency_s", "avg latency (s)", "{:.1f}"),
        ("avg_llm_calls", "avg LLM calls", "{:.1f}"),
    ]
    print("\n" + f"{'':<22}" + "".join(f"{s:>14}" for s in summaries))
    for key, label, fmt in rows:
        cells = [fmt.format(m[key]) if m[key] is not None else "–" for m in summaries.values()]
        print(f"{label:<22}" + "".join(f"{c:>14}" for c in cells))


if __name__ == "__main__":
    main()
