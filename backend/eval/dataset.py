"""The test set: questions with reference answers and the source sections that contain them."""

import json
from dataclasses import dataclass
from pathlib import Path

DATASET = Path(__file__).with_name("dataset.jsonl")
CATEGORIES = (
    "fact",  # one fact, stated plainly
    "paraphrase",  # worded differently from the document ("vacation" vs "paid time off")
    "identifier",  # hinges on an exact token (INC-2026-031, TT-200C, insufficient_scope)
    "table",  # answer sits in a PDF table
    "superseded",  # a newer document overrides an older one
    "multi_hop",  # needs facts from two places
    "arithmetic",  # needs a calculation on document numbers
    "date_math",  # needs a day count between document dates
    "unanswerable",  # not in the documents: the right answer is to refuse
)


@dataclass(frozen=True)
class ExpectedSource:
    """A labelled relevant section. Matching by document + heading (not chunk id) keeps the
    labels valid when chunking changes."""

    source: str  # substring of the document path, e.g. "employee_handbook"
    heading: str  # substring of one of the chunk's headings; "" matches any chunk of the document

    def matches(self, source: str, headings: list[str]) -> bool:
        return self.source in source and (not self.heading or any(self.heading in h for h in headings))


@dataclass(frozen=True)
class Question:
    id: str
    category: str
    question: str
    answer: str  # reference answer
    key_facts: tuple[str, ...]  # strings a correct answer must contain (checked without an LLM)
    sources: tuple[ExpectedSource, ...]
    answerable: bool = True


def load_dataset(path: Path = DATASET) -> list[Question]:
    questions = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        questions.append(
            Question(
                id=row["id"],
                category=row["category"],
                question=row["question"],
                answer=row["answer"],
                key_facts=tuple(row.get("key_facts", [])),
                sources=tuple(ExpectedSource(**s) for s in row.get("sources", [])),
                answerable=row.get("answerable", True),
            )
        )
    validate(questions)
    return questions


def validate(questions: list[Question]) -> None:
    """Catch labelling mistakes early: they would silently skew every metric."""
    ids = [q.id for q in questions]
    duplicates = {i for i in ids if ids.count(i) > 1}
    if duplicates:
        raise ValueError(f"duplicate question ids: {sorted(duplicates)}")
    for q in questions:
        if q.category not in CATEGORIES:
            raise ValueError(f"{q.id}: unknown category {q.category!r}")
        if q.answerable != (q.category != "unanswerable"):
            raise ValueError(f"{q.id}: only 'unanswerable' questions may set answerable=false")
        if q.answerable and not (q.sources and q.key_facts):
            raise ValueError(f"{q.id}: answerable questions need sources and key_facts")
