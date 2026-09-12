# Gen AI & Agentic AI — LangChain, LangGraph, and Full-Stack Load Handling

A learning path for building real GenAI/agentic applications with **LangChain** and **LangGraph**, and — the part most tutorials skip — what changes when you put one behind a full-stack app that has to serve more than one user at a time.

Every code example in [`examples/`](examples/) is real, runnable, and tested (most against a fake/mock model so they run without an API key — see each example's own README for how to switch to a real LLM).

## How to use this repo

Read in order if you're starting from zero:

1. [GenAI Fundamentals](docs/01-genai-fundamentals.md) — LLMs, tokens, embeddings, and why "just call the API" stops working past a toy demo.
2. [LangChain Basics](docs/02-langchain-basics.md) — LCEL, prompts, output parsers, memory, tools.
3. [LangGraph Basics](docs/03-langgraph-basics.md) — why graphs instead of chains: state, cycles, conditional routing.
4. [Agentic Patterns](docs/04-agentic-patterns.md) — ReAct, plan-and-execute, multi-agent, tool-calling — and when each earns its complexity.
5. [RAG Pipelines](docs/05-rag-pipelines.md) — chunking, embeddings, retrieval, and the failure modes that actually happen in production.
6. [Full-Stack Architecture](docs/06-fullstack-architecture.md) — wiring a LangChain/LangGraph backend to a real frontend: streaming tokens, SSE vs. WebSockets, where state actually lives.
7. [Load Handling](docs/07-load-handling.md) — the part this repo exists for: concurrency limits, queuing, backpressure, caching, and why LLM apps break under load differently than normal web apps.
8. [Observability & Evaluation](docs/08-observability-evaluation.md) — tracing, evals, guardrails — how you find out it's wrong before a user does.

## Examples

| Folder | What it demonstrates | Needs a real API key? |
|---|---|---|
| [`01-langchain-basics/`](examples/01-langchain-basics/) | An LCEL chain (`prompt \| model \| parser`), tested end-to-end with a fake model | No (fake model); yes to try it for real |
| [`02-langgraph-basics/`](examples/02-langgraph-basics/) | A small stateful graph with conditional routing between nodes | No |
| [`03-fullstack-streaming/`](examples/03-fullstack-streaming/) | A FastAPI backend streaming LLM tokens to the browser over Server-Sent Events | No (fake model) |
| [`04-load-handling/`](examples/04-load-handling/) | The same streaming API, now with a concurrency limit, a request queue, and backpressure (HTTP 429) under load — plus a load-test script that proves it | No |

Each example's own README says exactly how to run and test it. To run every example's tests at once (each isolated in its own subprocess — see [`run_all_tests.py`](run_all_tests.py) for why that matters): `pip install -r requirements.txt && python run_all_tests.py`.

## Beyond the examples: a production-shaped service

[`production-rag-service/`](production-rag-service/) is a separate, deeper build — not a teaching demo. It takes the load-handling ideas above and makes them actually production-grade: a **Redis-backed** distributed rate limiter and concurrency semaphore (correct across multiple running instances, not just one process), a **real database** for durable conversation history, and a full **RAG pipeline** (chunk → embed → store → retrieve → generate) behind a swappable vector store — an in-memory one for fast, dependency-free tests, and a real **pgvector** (Postgres) backend for production. 16 tests pass with zero external services; 2 more exercise the real pgvector SQL once you run `docker compose up -d postgres`. See its own [README](production-rag-service/README.md) for the full picture.

## Why LangChain *and* LangGraph, not just one

- **LangChain** is the right tool when the flow is basically linear: retrieve → prompt → generate → parse. Most RAG pipelines and single-turn tools live here.
- **LangGraph** earns its keep once the flow needs to **loop, branch on the model's own output, or coordinate multiple steps/agents with shared state** — a ReAct-style agent deciding whether to call a tool again, a multi-agent handoff, a human-in-the-loop approval step. Forcing that into a linear chain usually means fighting the abstraction; LangGraph models it directly as a graph.

See [docs/03-langgraph-basics.md](docs/03-langgraph-basics.md) for the concrete "which one do I reach for" decision guide.

## Prerequisites

- Python 3.10+
- `pip install -r requirements.txt` (or per-example `requirements.txt` files under `examples/*/`)
- An OpenAI API key (or another provider's) only if you want to run examples against a real model instead of the built-in fake one — see [docs/01-genai-fundamentals.md](docs/01-genai-fundamentals.md) for provider-agnostic notes.
