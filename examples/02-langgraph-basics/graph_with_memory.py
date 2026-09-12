"""
The current, non-deprecated way to persist state across calls in
LangChain/LangGraph — a checkpointer, keyed by `thread_id`. This is what
examples/01-langchain-basics/memory_chain.py's deprecation warning is
pointing you toward.

Run:
    python graph_with_memory.py
"""
from typing import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, StateGraph


class CounterState(TypedDict, total=False):
    count: int


def increment(state: CounterState) -> dict:
    return {"count": state.get("count", 0) + 1}


def build_graph():
    graph = StateGraph(CounterState)
    graph.add_node("increment", increment)
    graph.set_entry_point("increment")
    graph.add_edge("increment", END)

    # In-memory only — swap for a Postgres/SQLite checkpointer
    # (langgraph.checkpoint.postgres / .sqlite) for anything that needs to
    # survive a restart or run across multiple processes. See
    # docs/07-load-handling.md for why this matters at scale.
    checkpointer = InMemorySaver()
    return graph.compile(checkpointer=checkpointer)


if __name__ == "__main__":
    app = build_graph()

    session_a = {"configurable": {"thread_id": "session-a"}}
    session_b = {"configurable": {"thread_id": "session-b"}}

    print("session-a:", app.invoke({}, config=session_a))  # count: 1
    print("session-a:", app.invoke({}, config=session_a))  # count: 2
    print("session-b:", app.invoke({}, config=session_b))  # count: 1 — separate thread
