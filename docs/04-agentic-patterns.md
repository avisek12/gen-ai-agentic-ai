# Agentic Patterns

Builds directly on [docs/03-langgraph-basics.md](03-langgraph-basics.md) — read that first if you haven't. "Agentic" here means: the model's own output determines what happens next, not just what the final answer says.

## ReAct (Reason + Act)

The classic agent loop: the model reasons about what to do, optionally calls a tool, observes the result, and repeats until it decides it's done.

As a graph, this is [examples/02-langgraph-basics/graph.py](../examples/02-langgraph-basics/graph.py)'s shape, but with the tool-call edge **routing back** to the reasoning node instead of straight to `answer`:

```
reason --(needs tool?)--> call_tool --> reason --(needs tool?)--> ... --> answer --> END
       \--(no, done)---------------------------------------------------> answer --> END
```

The loop terminates because `reason` (a real LLM call, using `bind_tools` from [docs/02](02-langchain-basics.md)) eventually returns a response with no tool call — that's the signal to route to `answer` instead of back to `call_tool`. **A ReAct agent without a max-iteration guard can loop forever** if the model keeps deciding it needs another tool call — always cap iterations in the state (e.g., an `attempts` counter, route to `answer` unconditionally past a threshold) for anything customer-facing.

## Plan-and-execute

Instead of deciding one step at a time, the model produces a multi-step plan up front, then a separate loop executes each step (possibly re-planning if a step fails or reveals new information). This trades ReAct's flexibility for more predictable cost and latency — you know roughly how many LLM calls a run will take before you start, which matters directly for [docs/07-load-handling.md](07-load-handling.md)'s capacity planning.

## Multi-agent handoff

Multiple graphs (or multiple sets of nodes in one graph), each with a narrower system prompt/tool set, handing off to each other based on the task — e.g., a "router" node that decides whether a "billing agent" or a "technical agent" subgraph should handle a request. LangGraph models this as nodes that can themselves be compiled subgraphs, with the parent graph's state shared or explicitly passed down.

The main reason to reach for this over one big agent with every tool available: **a narrower system prompt and smaller tool set is more reliable** than one agent trying to juggle everything — the model makes fewer wrong tool choices when it has fewer, more relevant tools to choose from at any point.

## Human-in-the-loop

A node that pauses the graph and waits for a human decision (approve/reject/edit) before continuing — implemented via LangGraph's interrupt mechanism, which uses the same checkpointer from [docs/03](03-langgraph-basics.md) to persist state while waiting. This is the pattern for anything where a wrong agent action is costly enough that you want a person to confirm before it executes (sending an email, making a purchase, modifying production data).

## When agentic patterns are the wrong choice

Every one of these costs more latency and more tokens than a direct chain, and adds a failure mode a chain doesn't have (infinite loops, tool-call hallucination, cascading errors across a multi-agent handoff). If the task doesn't actually need the model to make a runtime decision — the flow really is retrieve-prompt-generate — a plain LangChain chain is not just simpler, it's more reliable. Reach for agentic patterns because the task genuinely needs them, not because they're the more interesting thing to build.
