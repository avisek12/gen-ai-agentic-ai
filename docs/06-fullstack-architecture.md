# Full-Stack Architecture

Runnable, tested code for everything here: [`examples/03-fullstack-streaming/`](../examples/03-fullstack-streaming/).

## Where each piece lives

```
Browser  <--SSE/WebSocket-->  Backend (FastAPI)  <-->  LangChain/LangGraph  <-->  LLM provider API
                                     |
                                     v
                              Vector store / DB (for RAG, memory)
```

The backend's job is thin on purpose: accept a request, run the chain/graph, stream the result back. Business logic (prompts, retrieval, tool definitions) belongs in the LangChain/LangGraph layer, not scattered into route handlers — that's what keeps it testable independent of the web framework (see how [`examples/03`](../examples/03-fullstack-streaming/)'s tests import `chain` directly, and [`examples/01`](../examples/01-langchain-basics/)'s tests never touch FastAPI at all).

## Streaming: SSE vs. WebSockets

This repo's examples use **Server-Sent Events (SSE)** — plain HTTP, one direction (server → browser), works through most proxies/load balancers with no special configuration. `StreamingResponse` + `text/event-stream` on the backend, `EventSource` in the browser — see [`examples/03/server.py`](../examples/03-fullstack-streaming/server.py) and [`static/index.html`](../examples/03-fullstack-streaming/static/index.html) for the full working pair.

Reach for **WebSockets** instead when you need the *browser* to send data back mid-stream — the user interrupting/redirecting the model while it's still generating, or a multi-party chat. That's a genuinely different problem (bidirectional, stateful connection) — don't reach for it by default just because it sounds more "real-time"; SSE is simpler and sufficient for most chat UIs.

## Why streaming is nearly free with LangChain/LangGraph

`chain.astream(...)` and a graph's `.astream()` both work because every LCEL `Runnable` implements streaming — you don't write token-buffering logic yourself. The FastAPI side is just: an `async def` endpoint, an `async for` over the chain's stream, `yield`ing each chunk formatted as an SSE `data:` line. This is confirmed by [`examples/03`](../examples/03-fullstack-streaming/)'s actual tests, which check the response really does arrive as multiple SSE lines, not one chunk pretending to be a stream.

## Where state actually lives

- **Per-request state** (the current question, retrieved context) — just function arguments/local variables, nothing special.
- **Per-conversation state** (chat history) — a LangGraph checkpointer keyed by a session/thread id (see [docs/03](03-langgraph-basics.md)), or the older `RunnableWithMessageHistory` pattern (see [docs/02](02-langchain-basics.md), and note its own deprecation warning).
- **Cross-user state that must survive a restart or work across multiple server processes** — this is exactly where an in-memory dict (what every example in this repo uses, for simplicity) stops being enough. See [docs/07-load-handling.md](07-load-handling.md).

## A concrete architecture decision this repo made, and why

Every example's backend is a thin FastAPI app with the LangChain/LangGraph logic in plain, framework-independent Python modules imported by it — not, e.g., logic embedded directly in route handler bodies. The payoff shows up directly in the test suites: [`examples/01`](../examples/01-langchain-basics/) and [`examples/02`](../examples/02-langgraph-basics/)'s tests never start a web server at all, and [`examples/03`](../examples/03-fullstack-streaming/)'s and [`examples/04`](../examples/04-load-handling/)'s web-layer tests import the same chain/graph objects rather than re-implementing them. Structure your own project the same way — it's the difference between testing your actual logic and only ever testing it through HTTP.
