"""
A minimal LangGraph state graph demonstrating the thing a linear LangChain
chain can't do cleanly: branch based on a decision made mid-flow.

Flow:
    classify -> (needs a tool?) -> call_tool -> answer -> END
                                 -> answer -> END

`classify` uses plain Python logic here to keep the example fast and
deterministic to test; in a real app it's an LLM call deciding whether a
tool is needed (see docs/04-agentic-patterns.md for the real ReAct pattern
using an LLM's own tool-calling output instead of keyword matching).

Run:
    python graph.py
"""
from typing import Literal, TypedDict

from langgraph.graph import END, StateGraph


class GraphState(TypedDict, total=False):
    question: str
    needs_tool: bool
    tool_result: str
    answer: str


def classify(state: GraphState) -> dict:
    # Stand-in for an LLM call deciding whether it needs a tool.
    needs_tool = "weather" in state["question"].lower()
    return {"needs_tool": needs_tool}


def call_tool(state: GraphState) -> dict:
    # Stand-in for a real tool call (an API, a DB lookup, ...).
    return {"tool_result": "Sunny, 22C"}


def answer(state: GraphState) -> dict:
    if state.get("tool_result"):
        return {"answer": f"Based on the tool: {state['tool_result']}"}
    return {"answer": f"Direct answer to: {state['question']}"}


def route_after_classify(state: GraphState) -> Literal["call_tool", "answer"]:
    return "call_tool" if state["needs_tool"] else "answer"


def build_graph():
    graph = StateGraph(GraphState)
    graph.add_node("classify", classify)
    graph.add_node("call_tool", call_tool)
    graph.add_node("answer", answer)

    graph.set_entry_point("classify")
    graph.add_conditional_edges(
        "classify", route_after_classify, {"call_tool": "call_tool", "answer": "answer"}
    )
    graph.add_edge("call_tool", "answer")
    graph.add_edge("answer", END)

    return graph.compile()


if __name__ == "__main__":
    app = build_graph()

    print(app.invoke({"question": "What's the weather like today?"}))
    print(app.invoke({"question": "What is 2 + 2?"}))
