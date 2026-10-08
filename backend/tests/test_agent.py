import os
import re

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.agent import nodes
from app.agent.graph import _after_grade, _after_model, ask, build_graph


def source(n, chunk_id=None):
    return {"n": n, "chunk_id": chunk_id or n, "title": "T", "source": "s", "citation": f"C{n}", "content": "x"}


# ---------------------------------------------------------------- unit tests (no API calls)


def test_finish_keeps_only_citations_that_match_a_source():
    out = nodes._finish("A [1]. B [2][3]. C [1, 3]. D [9].", [source(1), source(2), source(3)])
    assert [s["n"] for s in out["citations"]] == [1, 2, 3]  # [9] doesn't exist and is ignored
    assert isinstance(out["messages"][0], AIMessage)


def test_new_sources_are_numbered_after_existing_ones():
    merged = nodes._append_numbered([source(1), source(2)], [source(0, chunk_id=10), source(0, chunk_id=11)])
    assert [s["n"] for s in merged] == [1, 2, 3, 4]


def test_grading_loop_retries_once_then_gives_up():
    assert _after_grade({"sources": [], "queries": ["q1"]}) == "rewrite"
    assert _after_grade({"sources": [], "queries": ["q1", "q2"]}) == "generate"
    assert _after_grade({"sources": [source(1)], "queries": ["q1"]}) == "generate"


def test_model_step_loops_through_tools_until_there_is_an_answer():
    assert _after_model({"answer": ""}) == "tools"
    assert _after_model({"answer": "Done [1]."}) == "__end__"


def test_refusal_does_not_call_the_model(monkeypatch):
    monkeypatch.setattr(nodes, "get_chat_model", lambda: pytest.fail("the model must not be called"))
    out = nodes.generate(
        {"sources": [], "queries": ["a", "b"], "scratch": [], "question": "q", "messages": [HumanMessage("q")]}
    )
    assert "couldn't find" in out["answer"]
    assert out["citations"] == []


def test_graph_has_the_retry_and_tool_loops():
    edges = {(e.source, e.target) for e in build_graph().get_graph().edges}
    assert {("grade", "rewrite"), ("rewrite", "retrieve"), ("generate", "tools"), ("tools", "generate")} <= edges


# ---------------------------------------------------------------- live tests (opt-in: they use Gemini quota)

live = pytest.mark.skipif(
    os.getenv("RUN_AGENT_TESTS") != "1", reason="uses Gemini chat quota; run with RUN_AGENT_TESTS=1"
)


@live
def test_newer_policy_wins_over_the_handbook():
    state = ask("How many unused PTO days can I carry over into next year?")
    assert "8" in state["answer"]
    assert any("hr_policy_update" in c["source"] for c in state["citations"])


@live
def test_unanswerable_question_is_refused():
    state = ask("What is Brindlewave's stock ticker symbol?")
    assert state["citations"] == []
    assert "couldn't find" in state["answer"]


@live
def test_greeting_skips_retrieval():
    state = ask("Hello!")
    assert state["route"] == "direct"
    assert state["queries"] == []


@live
def test_pricing_math_uses_the_calculator():
    state = ask("What would 12 sites on the Growth plan cost per year, including the volume discount?")
    tools_called = [c["name"] for m in state["scratch"] if isinstance(m, AIMessage) for c in m.tool_calls]
    assert "calculator" in tools_called
    assert "581904" in re.sub(r"\D", "", state["answer"])  # €58,190.40 in any number format
