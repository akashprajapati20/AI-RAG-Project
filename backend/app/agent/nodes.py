"""The graph's nodes. Each takes the current state and returns only the fields it changes."""

import re
from datetime import date
from typing import Literal

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage, ToolMessage
from pydantic import BaseModel, Field

from app.agent import prompts
from app.agent.state import AgentState, Source
from app.agent.tools import ANSWER_TOOLS, GENERAL_TOOLS, LOCAL_TOOLS
from app.llm import get_chat_model, get_fast_model
from app.retrieval import RetrievedChunk, search

RETRIEVE_K = 6  # chunks per search, handed to the grader
MAX_SEARCHES = 2  # the first search + one rewrite
MAX_TOOL_ROUNDS = 4  # tool-calling rounds per answer before the model must reply in text
HISTORY_MESSAGES = 6  # earlier conversation messages shown to the model, for follow-ups


# ---------------------------------------------------------------- structured outputs


class RouteDecision(BaseModel):
    route: Literal["retrieve", "tools", "direct"]
    query: str = Field(description="the latest message as a standalone search query")


class GradeResult(BaseModel):
    relevant: list[int] = Field(description="numbers of the passages that help answer the question")


class RewrittenQuery(BaseModel):
    query: str


# ---------------------------------------------------------------- nodes


def router(state: AgentState) -> dict:
    question = state["messages"][-1].text
    decision = get_fast_model().with_structured_output(RouteDecision).invoke(
        [SystemMessage(prompts.ROUTER), HumanMessage(f"{_history(state)}Latest message: {question}")]
    )
    # A new turn: reset every per-turn field. The conversation in `messages` carries over.
    return {
        "question": question,
        "route": decision.route,
        "query": decision.query.strip() or question,
        "queries": [],
        "candidates": [],
        "sources": [],
        "scratch": [],
        "answer": "",
        "citations": [],
    }


def retrieve(state: AgentState) -> dict:
    results = search(state["query"], k=RETRIEVE_K)
    return {
        "candidates": [_to_source(chunk, n) for n, chunk in enumerate(results, start=1)],
        "queries": state["queries"] + [state["query"]],
    }


def grade(state: AgentState) -> dict:
    """Keep only the candidates that actually help. Search always returns k results, even for
    questions the documents can't answer; this is where irrelevant ones are dropped."""
    candidates = state["candidates"]
    if not candidates:
        return {}
    verdict = get_fast_model().with_structured_output(GradeResult).invoke(
        [
            SystemMessage(prompts.GRADER),
            HumanMessage(f"Question: {state['question']}\n\n{format_sources(candidates)}"),
        ]
    )
    known = {s["chunk_id"] for s in state["sources"]}
    keep = [c for c in candidates if c["n"] in set(verdict.relevant) and c["chunk_id"] not in known]
    return {"sources": _append_numbered(state["sources"], keep)}


def rewrite(state: AgentState) -> dict:
    tried = "\n".join(f"- {q}" for q in state["queries"])
    result = get_fast_model().with_structured_output(RewrittenQuery).invoke(
        [
            SystemMessage(prompts.REWRITER),
            HumanMessage(f"Question: {state['question']}\n\nQueries already tried:\n{tried}"),
        ]
    )
    return {"query": result.query}


def generate(state: AgentState) -> dict:
    """Grounded answer from the numbered sources, citing them as [n]."""
    sources = state["sources"]
    if not sources:
        # Nothing relevant after every search: refuse without calling the model, so it can't
        # "helpfully" invent an answer.
        tried = ", ".join(f"'{q}'" for q in state["queries"])
        return _finish(prompts.NO_ANSWER.format(queries=tried), [])
    scratch = state["scratch"] or [
        HumanMessage(f"{_history(state)}Sources:\n\n{format_sources(sources)}\n\nQuestion: {state['question']}")
    ]
    return _model_step(prompts.ANSWER, scratch, ANSWER_TOOLS, sources)


def respond(state: AgentState) -> dict:
    """Small talk, general questions and pure calculations: no documents involved."""
    scratch = state["scratch"] or [HumanMessage(f"{_history(state)}Message: {state['question']}")]
    return _model_step(prompts.RESPOND, scratch, GENERAL_TOOLS, [])


def run_tools(state: AgentState) -> dict:
    """Execute the tool calls from the model's last message and add the results to scratch."""
    sources, queries = list(state.get("sources", [])), list(state.get("queries", []))
    results: list[AnyMessage] = []
    for call in state["scratch"][-1].tool_calls:
        if call["name"] == "search_knowledge_base":
            # Handled here rather than in the tool: results become new numbered sources.
            query = call["args"].get("query", "")
            known = {s["chunk_id"] for s in sources}
            new = [_to_source(c, 0) for c in search(query, k=RETRIEVE_K) if c.chunk_id not in known]
            sources = _append_numbered(sources, new)
            queries.append(query)
            content = format_sources(sources[-len(new) :]) if new else "No new passages found."
        elif call["name"] in LOCAL_TOOLS:
            content = LOCAL_TOOLS[call["name"]].invoke(call["args"])
        else:
            content = f"Error: unknown tool {call['name']!r}"
        results.append(ToolMessage(content=content, tool_call_id=call["id"], name=call["name"]))
    return {"scratch": state["scratch"] + results, "sources": sources, "queries": queries}


# ---------------------------------------------------------------- helpers

_CITATION = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")  # [2], [1][3] and [1, 3]


def _model_step(system_prompt: str, scratch: list[AnyMessage], tools: list, sources: list[Source]) -> dict:
    """One model turn: it either asks for tools (the graph runs them and comes back) or answers."""
    rounds = sum(isinstance(m, AIMessage) for m in scratch)
    # After MAX_TOOL_ROUNDS, keep the tools declared (the history contains calls to them) but
    # forbid new calls, so the model has to answer with what it has.
    model = get_chat_model().bind_tools(tools, tool_choice="none" if rounds >= MAX_TOOL_ROUNDS else None)
    today = date.today()
    reply = model.invoke([SystemMessage(system_prompt.format(today=f"{today:%A} {today.isoformat()}"))] + scratch)
    if reply.tool_calls:
        return {"scratch": scratch + [reply]}
    return {"scratch": scratch + [reply], **_finish(reply.text or "Sorry, I couldn't produce an answer.", sources)}


def _finish(answer: str, sources: list[Source]) -> dict:
    """Record the final answer and which sources it cites, and add it to the conversation.
    Citation numbers that don't match a source are ignored."""
    citations = cited_sources(answer, sources)
    return {
        "answer": answer,
        "citations": citations,
        # Citations ride along on the stored message so a reloaded conversation can show them;
        # the model never sees them (_history only uses message text).
        "messages": [AIMessage(answer, additional_kwargs={"citations": citations})],
    }


def cited_sources(answer: str, sources: list[Source]) -> list[Source]:
    """The sources an answer cites as [n]; numbers that match no source are ignored."""
    cited = {int(n) for group in _CITATION.findall(answer) for n in group.split(",")}
    return [s for s in sources if s["n"] in cited]


def format_sources(sources: list[Source]) -> str:
    return "\n\n".join(f"[{s['n']}] {s['citation']}\n{s['content']}" for s in sources)


def _to_source(chunk: RetrievedChunk, n: int) -> Source:
    return Source(
        n=n,
        chunk_id=chunk.chunk_id,
        title=chunk.title,
        source=chunk.source,
        citation=chunk.citation,
        content=chunk.content,
    )


def _append_numbered(existing: list[Source], new: list[Source]) -> list[Source]:
    """Append new sources, numbering them after the existing ones: [1..n] stay stable."""
    return existing + [{**s, "n": len(existing) + i} for i, s in enumerate(new, start=1)]


def _history(state: AgentState) -> str:
    """The earlier conversation (not the latest message), for resolving follow-up questions."""
    earlier = state["messages"][:-1][-HISTORY_MESSAGES:]
    if not earlier:
        return ""
    lines = [f"{'User' if m.type == 'human' else 'Assistant'}: {m.text[:600]}" for m in earlier]
    return "Conversation so far:\n" + "\n".join(lines) + "\n\n"
