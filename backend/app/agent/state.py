"""The agent's state: the data every graph node reads from and writes to."""

from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class Source(TypedDict):
    n: int  # the number the model cites, as in [n]
    chunk_id: int
    title: str
    source: str  # file, e.g. "data/corpus/pricing_and_plans_2026.pdf"
    citation: str  # e.g. "Tally Pricing and Plans 2026 › 4. SLA credits (p. 1)"
    content: str


class AgentState(TypedDict, total=False):
    # The conversation, kept across turns. add_messages appends instead of replacing.
    messages: Annotated[list[AnyMessage], add_messages]

    # Per-turn working data; the router resets all of it when a new question arrives.
    question: str  # the latest user message
    route: str  # "retrieve" | "tools" | "direct"
    query: str  # the current search query (standalone; may be rewritten)
    queries: list[str]  # every search query tried this turn
    candidates: list[Source]  # latest search results, before grading
    sources: list[Source]  # graded-relevant sources, numbered 1..n for citation
    scratch: list[AnyMessage]  # this turn's prompt + tool-calling exchange with the model
    answer: str
    citations: list[Source]  # the sources the final answer actually cites
