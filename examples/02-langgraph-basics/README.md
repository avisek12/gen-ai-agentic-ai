# 02 — LangGraph Basics

Two runnable files:

- **`graph.py`** — a state graph with **conditional routing**: a `classify` node decides whether to route through `call_tool` before `answer`, or skip straight to `answer`. This is the shape a linear LangChain chain can't express cleanly — the decision of *which node runs next* is made at runtime, based on state.
- **`graph_with_memory.py`** — the current, non-deprecated way to persist state across calls: a **checkpointer** keyed by `thread_id`. This is what replaces LangChain's `RunnableWithMessageHistory` (see [01-langchain-basics](../01-langchain-basics/)'s deprecation note).

## Run

```
pip install -r requirements.txt
python graph.py
python graph_with_memory.py
```

## Test

```
pytest test_graph.py -v
```

## Why this matters vs. a LangChain chain

`graph.py`'s `classify` function returns a plain dict here (deterministic, for a fast test) — in a real app it's an LLM call, and the LLM's own output decides which branch runs. Once you need that — the model's own decision changing the control flow, possibly looping back (a ReAct agent retrying a tool call) — you're in LangGraph's territory, not LangChain's. See [docs/03-langgraph-basics.md](../../docs/03-langgraph-basics.md) for the full decision guide.
