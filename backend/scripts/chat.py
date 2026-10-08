"""Chat with the agent in the terminal.

Usage (from backend/):
    python -m scripts.chat                                          # interactive, remembers the conversation
    python -m scripts.chat "How many PTO days can I carry over?"    # a single question
    python -m scripts.chat --trace "..."                            # also print every step the agent takes
"""

import argparse
import time
import uuid

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from app.agent.graph import build_graph
from app.agent.trace import describe_step
from app.llm import friendly_error


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("question", nargs="?", help="ask one question and exit")
    parser.add_argument("--trace", action="store_true", help="print each step of the agent")
    args = parser.parse_args()

    graph = build_graph(checkpointer=InMemorySaver())  # memory for this session
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}

    if args.question:
        ask(graph, config, args.question, args.trace)
        return
    print("Ask about Brindlewave. Type 'exit' or press Ctrl-D to quit.")
    while True:
        try:
            question = input("\nyou> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if question.lower() in {"exit", "quit"}:
            break
        if question:
            ask(graph, config, question, args.trace)


def ask(graph, config: dict, question: str, trace: bool) -> None:
    started = step_started = time.perf_counter()
    try:
        for update in graph.stream({"messages": [HumanMessage(question)]}, config, stream_mode="updates"):
            for node, changes in update.items():
                if trace:
                    now = time.perf_counter()
                    print(f"  · {now - step_started:5.1f}s  {node:<8} {describe_step(node, changes or {})['label']}")
                    step_started = now
    except Exception as e:
        print(f"\n[{friendly_error(e)}]")
        return

    state = graph.get_state(config).values
    print(f"\nassistant> {state['answer'].strip()}")
    if state["citations"]:
        print("\nSources:")
        for s in state["citations"]:
            print(f"  [{s['n']}] {s['citation']}")
    if trace:
        print(f"\n({time.perf_counter() - started:.1f}s total)")


if __name__ == "__main__":
    main()
