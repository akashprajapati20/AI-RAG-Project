# Evaluation report

_Generated 2026-10-05 12:04 by `python -m eval.report` from `eval/results/`._

## Test set

41 questions about the Brindlewave corpus, written with reference answers, key facts and labelled source sections (`eval/dataset.jsonl`).

| Category | Questions | What it tests |
|---|---|---|
| fact | 10 | one fact, stated plainly |
| paraphrase | 4 | different wording from the document ("vacation" vs "paid time off") |
| identifier | 4 | an exact token (INC-2026-031, TT-200C, insufficient_scope) |
| table | 4 | an answer inside a PDF table |
| superseded | 3 | a newer memo overrides the handbook |
| multi_hop | 4 | facts from two places |
| arithmetic | 4 | a calculation on document numbers |
| date_math | 2 | a day count between document dates |
| unanswerable | 6 | not documented: the right answer is to refuse |

## Retrieval

Each answerable question (35) is searched with every mode; a result is relevant if it comes from a labelled document section. **Hit@k**: a relevant result in the top k. **Recall@5**: share of all labelled sections in the top 5. **MRR**: mean of 1/rank of the first relevant result.

| Mode | Hit@1 | Hit@3 | Hit@5 | Recall@5 | MRR |
|---|---|---|---|---|---|
| vector | 94% | 100% | 100% | 100% | 0.967 |
| keyword | 86% | 97% | 100% | 99% | 0.921 |
| hybrid | 97% | 100% | 100% | 100% | 0.986 |

MRR by category:

| Category | vector | keyword | hybrid |
|---|---|---|---|
| fact | 1.00 | 0.95 | 1.00 |
| paraphrase | 1.00 | 1.00 | 1.00 |
| identifier | 1.00 | 0.88 | 1.00 |
| table | 0.83 | 0.81 | 1.00 |
| superseded | 1.00 | 1.00 | 1.00 |
| multi_hop | 0.88 | 1.00 | 0.88 |
| arithmetic | 1.00 | 0.88 | 1.00 |
| date_math | 1.00 | 0.75 | 1.00 |

## Answer quality

Answer model **gemini-3.5-flash-lite** for every system; judge **gemini-3.5-flash-lite**; the agent's router/grader/rewriter use **gemini-3.5-flash-lite**.

- **closed_book**: the model alone, no documents.
- **plain_rag**: one hybrid search (top 6) + one answer call with the same grounding and citation rules.
- **agent**: routing, LLM relevance grading, one query rewrite, tools, deterministic refusal.

| Metric | closed_book | plain_rag | agent |
|---|---|---|---|
| Questions answered | 41 | 41 | 41 |
| Accuracy (answerable; partial = ½) | 13% | 100% | 97% |
| Key facts present (deterministic) | 9% | 100% | 97% |
| **Hallucination rate** (any unsupported claim) | 90% | 0% | 2% |
| Refused unanswerable questions | 0% | 100% | 100% |
| Refused answerable questions | 3% | 0% | 0% |
| Answers with ≥1 citation | – | 89% | 100% |
| Citations pointing to a labelled document | – | 98% | 98% |
| Avg latency (s) | 5.0 | 6.9 | 17.9 |
| Avg LLM calls per question | 1.0 | 1.0 | 3.3 |
| Avg tokens per question | 67 | 1,774 | 3,276 |

### By category

Accuracy per category (for *unanswerable*: share correctly refused).

| Category | n | closed_book | plain_rag | agent |
|---|---|---|---|---|
| fact | 10 | 20% | 100% | 100% |
| paraphrase | 4 | 38% | 100% | 100% |
| identifier | 4 | 0% | 100% | 100% |
| table | 4 | 0% | 100% | 100% |
| superseded | 3 | 0% | 100% | 100% |
| multi_hop | 4 | 25% | 100% | 100% |
| arithmetic | 4 | 0% | 100% | 75% |
| date_math | 2 | 0% | 100% | 100% |
| unanswerable | 6 | 0% | 100% | 100% |

### agent: wrong, partial or unsupported answers (1)

- **math-nonprofit-discount** (arithmetic) — *incorrect*: A nonprofit has 60 sites on the Growth plan. Which discount applies, and what is the monthly price per site?
  - Answer: The 18% volume discount applies [1]. Volume discounts and nonprofit/education discounts do not stack, and the larger discount applies; the 18% volume discount for 50 or more sites is larger than the 25% nonprofit discount [1]. The monthly price per site is €368.18 (calculated as €449 discounted by 1…
  - Unsupported: the 18% volume discount for 50 or more sites is larger than the 25% nonprofit discount; The monthly price per site is €368.18
  - Judge: The assistant incorrectly stated that an 18% discount is larger than a 25% discount, leading to the wrong price calculation.

## Caveats

- **Small test set** (one run, ~40 questions): differences of a few points are within noise.
- **LLM-as-judge**: correctness and unsupported claims are graded by a Gemini model, which can be wrong and may favour answers from its own model family. The deterministic key-fact check is a cross-check.
- **Free-tier models**: answers here come from the model listed under *Answer quality*; the production default (`CHAT_MODEL`) may score differently.
