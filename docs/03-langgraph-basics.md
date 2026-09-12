# LangGraph Basics

Runnable, tested code for everything here: [`examples/02-langgraph-basics/`](../examples/02-langgraph-basics/).

## The core idea: state + nodes + edges

A LangGraph graph has three parts:

- **State** — a `TypedDict` describing what flows through the graph. Each node reads it and returns a partial update (a dict of just the keys it changed) — LangGraph merges that into the running state.
- **Nodes** — plain functions, `(state) -> dict`. A node can be an LLM call, a tool call, or just Python logic.
- **Edges** — how nodes connect. A normal edge always goes to the same next node. A **conditional edge** picks the next node at runtime based on the current state:

```python
graph.add_conditional_edges(
    "classify", route_after_classify, {"call_tool": "call_tool", "answer": "answer"}
)
```

`route_after_classify` is a function that inspects `state` and returns a string key — LangGraph looks that key up in the mapping to decide the next node. This is the mechanism that makes branching (and, with an edge back to an earlier node, looping) possible.

## Which one do I reach for — LangChain or LangGraph?

| Your flow is... | Use |
|---|---|
| Retrieve → prompt → generate → parse, always in that order | LangChain (LCEL chain) |
| The model's own output decides what happens next (call a tool, ask a follow-up, stop) | LangGraph |
| A step might need to repeat (a ReAct agent retrying a tool call until it gets a usable result) | LangGraph — chains can't loop, graphs can (an edge back to an earlier node) |
| Multiple agents/roles need to hand off to each other with shared state | LangGraph |
| You need durable, resumable state across a conversation or a long-running process | LangGraph's checkpointer — see below |

A useful rule of thumb: **if you can draw your flow as a straight line, use LangChain. The moment you draw an arrow going backward or a diamond (decision point), reach for LangGraph.**

## Persistence: the checkpointer

This is the current, non-deprecated way to persist state across calls — confirmed by testing it directly (LangChain's own `RunnableWithMessageHistory` now recommends this instead, see [docs/02](02-langchain-basics.md)):

```python
from langgraph.checkpoint.memory import InMemorySaver

checkpointer = InMemorySaver()
app = graph.compile(checkpointer=checkpointer)

app.invoke({}, config={"configurable": {"thread_id": "session-1"}})
```

Every invocation with the same `thread_id` continues from where that thread left off; a different `thread_id` starts fresh. `InMemorySaver` only lives in one process's memory — exactly the same limitation flagged in [docs/07-load-handling.md](07-load-handling.md) for any in-memory state: it doesn't survive a restart and doesn't work across multiple processes/instances. LangGraph also ships Postgres and SQLite checkpointer backends for when that matters.

## A minimal agentic loop, conceptually

```
classify --(needs tool?)--> call_tool --> answer --> END
        \--(no)-----------------------> answer --> END
```

This is deliberately the simplest possible branching graph — one decision, no loop. [docs/04-agentic-patterns.md](04-agentic-patterns.md) builds this into an actual ReAct-style loop, where `call_tool` can route back to `classify` instead of straight to `answer`, repeating until the model decides it has enough information.
