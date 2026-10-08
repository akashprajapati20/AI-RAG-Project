"""The three systems under test, each answering one question with the same answer model.

- closed_book: the model alone, no documents. Shows what the model makes up about a company it
  has never seen.
- plain_rag: one hybrid search (k=6) and one answer call with the same grounding and citation
  rules as the agent. No routing, grading, query rewriting, tools or deterministic refusal.
- agent: the full LangGraph agent from Part 4.

Comparing plain_rag with agent isolates what the agent's extra machinery adds.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import HumanMessage, SystemMessage

from app.agent.graph import default_graph
from app.agent.nodes import RETRIEVE_K, _to_source, cited_sources, format_sources
from app.llm import get_chat_model
from app.retrieval import search


@dataclass
class SystemOutput:
    answer: str
    sources: list[dict] = field(default_factory=list)  # every passage the system saw
    citations: list[dict] = field(default_factory=list)  # the passages its answer cites
    tool_results: list[str] = field(default_factory=list)  # e.g. "449 * 12 * 12 * 0.9 = 58190.4"
    details: dict = field(default_factory=dict)  # system-specific (route, queries, …)
    llm_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    latency_s: float = 0.0


class UsageCounter(BaseCallbackHandler):
    """Counts model calls and tokens. LangGraph passes callbacks down to every model call inside
    its nodes, so this also sees the agent's router, grader and rewriter calls."""

    def __init__(self) -> None:
        self.calls = self.input_tokens = self.output_tokens = 0

    def on_chat_model_start(self, serialized, messages, **kwargs) -> None:
        self.calls += 1

    def on_llm_end(self, response, **kwargs) -> None:
        for generations in response.generations:
            for generation in generations:
                usage = getattr(getattr(generation, "message", None), "usage_metadata", None) or {}
                self.input_tokens += usage.get("input_tokens", 0)
                self.output_tokens += usage.get("output_tokens", 0)


CLOSED_BOOK_PROMPT = "You are Brindlewave's internal knowledge assistant. Answer the employee's question concisely."

PLAIN_RAG_PROMPT = """You are Brindlewave's internal knowledge assistant. Today is {today}.
Answer the question using ONLY the numbered sources provided. Cite the sources that support each \
statement in square brackets, e.g. [2]. If the sources don't contain the answer, say so plainly; \
never guess. If sources disagree, prefer the more recent one. Be concise."""


def closed_book(question: str) -> SystemOutput:
    return _timed(lambda counter: _closed_book(question, counter))


def plain_rag(question: str) -> SystemOutput:
    return _timed(lambda counter: _plain_rag(question, counter))


def agent(question: str) -> SystemOutput:
    return _timed(lambda counter: _agent(question, counter))


SYSTEMS: dict[str, Callable[[str], SystemOutput]] = {
    "closed_book": closed_book,
    "plain_rag": plain_rag,
    "agent": agent,
}


def _closed_book(question: str, counter: UsageCounter) -> SystemOutput:
    reply = get_chat_model().invoke(
        [SystemMessage(CLOSED_BOOK_PROMPT), HumanMessage(question)], config={"callbacks": [counter]}
    )
    return SystemOutput(answer=reply.text)


def _plain_rag(question: str, counter: UsageCounter) -> SystemOutput:
    sources = [_to_source(chunk, n) for n, chunk in enumerate(search(question, k=RETRIEVE_K), start=1)]
    prompt = PLAIN_RAG_PROMPT.format(today=date.today().isoformat())
    reply = get_chat_model().invoke(
        [SystemMessage(prompt), HumanMessage(f"Sources:\n\n{format_sources(sources)}\n\nQuestion: {question}")],
        config={"callbacks": [counter]},
    )
    return SystemOutput(answer=reply.text, sources=sources, citations=cited_sources(reply.text, sources))


def _agent(question: str, counter: UsageCounter) -> SystemOutput:
    state = default_graph().invoke({"messages": [HumanMessage(question)]}, config={"callbacks": [counter]})
    # search_knowledge_base results are already in state["sources"]; keep the other tool outputs.
    tool_results = [m.content for m in state["scratch"] if m.type == "tool" and m.name != "search_knowledge_base"]
    return SystemOutput(
        answer=state["answer"],
        sources=state["sources"],
        citations=state["citations"],
        tool_results=tool_results,
        details={"route": state["route"], "queries": state["queries"]},
    )


def _timed(run: Callable[[UsageCounter], SystemOutput]) -> SystemOutput:
    counter = UsageCounter()
    started = time.perf_counter()
    output = run(counter)
    output.latency_s = time.perf_counter() - started
    output.llm_calls, output.input_tokens, output.output_tokens = counter.calls, counter.input_tokens, counter.output_tokens
    return output
