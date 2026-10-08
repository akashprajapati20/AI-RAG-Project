"""Wire the nodes into a LangGraph state machine.

    START → router ─retrieve─→ retrieve → grade ─relevant found / out of retries─→ generate ⇄ tools → END
                   │                        ↑        └─nothing relevant─→ rewrite ─┘
                   └─tools / direct─→ respond ⇄ tools → END
"""

from functools import lru_cache

from langchain_core.messages import HumanMessage
from langgraph.graph import END, START, StateGraph
from langgraph.types import Checkpointer

from app.agent import nodes
from app.agent.state import AgentState


def build_graph(checkpointer: Checkpointer = None):
    """Compile the agent. Pass a checkpointer (e.g. InMemorySaver) to remember conversations
    per thread_id; without one, every invocation starts fresh."""
    graph = StateGraph(AgentState)
    graph.add_node("router", nodes.router)
    graph.add_node("retrieve", nodes.retrieve)
    graph.add_node("grade", nodes.grade)
    graph.add_node("rewrite", nodes.rewrite)
    graph.add_node("generate", nodes.generate)
    graph.add_node("respond", nodes.respond)
    graph.add_node("tools", nodes.run_tools)

    graph.add_edge(START, "router")
    graph.add_conditional_edges("router", _after_router, ["retrieve", "respond"])
    graph.add_edge("retrieve", "grade")
    graph.add_conditional_edges("grade", _after_grade, ["generate", "rewrite"])
    graph.add_edge("rewrite", "retrieve")
    graph.add_conditional_edges("generate", _after_model, ["tools", END])
    graph.add_conditional_edges("respond", _after_model, ["tools", END])
    graph.add_conditional_edges("tools", _after_tools, ["generate", "respond"])
    return graph.compile(checkpointer=checkpointer)


def _after_router(state: AgentState) -> str:
    return "retrieve" if state["route"] == "retrieve" else "respond"


def _after_grade(state: AgentState) -> str:
    if state["sources"] or len(state["queries"]) >= nodes.MAX_SEARCHES:
        return "generate"  # generate refuses by itself if there are still no sources
    return "rewrite"


def _after_model(state: AgentState) -> str:
    return END if state.get("answer") else "tools"


def _after_tools(state: AgentState) -> str:
    return "generate" if state["route"] == "retrieve" else "respond"


@lru_cache
def default_graph():
    return build_graph()


def ask(question: str) -> AgentState:
    """Answer one question with no conversation memory (used by tests and the evaluation)."""
    return default_graph().invoke({"messages": [HumanMessage(question)]})
