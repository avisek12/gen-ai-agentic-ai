# Load Handling

Runnable, tested code for everything here: [`examples/04-load-handling/`](../examples/04-load-handling/) — including a real load test measured against a live server, not illustrative numbers.

## Why LLM apps break under load differently than normal web apps

A typical CRUD endpoint finishes in milliseconds — a burst of concurrent requests mostly just queues briefly behind each other and drains fast. An LLM call ties up a connection for **seconds**, not milliseconds. That difference compounds: accept an unbounded burst of slow requests and you don't get "everything is a little slower" — you get every single one of them crawling together, because the process is splitting its attention across all of them at once with none prioritized.

This is not a hypothetical — it's measured. [`examples/04-load-handling`](../examples/04-load-handling/)'s README has the real numbers from firing 60 concurrent requests at both an unprotected server and a protected one:

| | Unprotected | Protected (concurrency limit + backpressure) |
|---|---|---|
| Status codes | 60× `200` | 21× `200`, 39× `429` |
| Request duration | **every one** took 2.76–2.83s | successes 0.42–2.16s; rejections near-instant |

The unprotected server accepted everything and made **all 60** requests slow. The protected one rejected what it couldn't serve promptly, fast, and kept what it did accept within a known concurrency budget.

## The core technique: cap concurrency, reject fast past the cap

```python
try:
    await asyncio.wait_for(semaphore.acquire(), timeout=QUEUE_WAIT_TIMEOUT_SECONDS)
except asyncio.TimeoutError:
    raise HTTPException(status_code=429, detail="Server is at capacity.")
```

Two numbers to tune deliberately, not guess:
- **The concurrency limit** — size it against your actual LLM provider's rate limit (requests/min, tokens/min), not an arbitrary number. There's no point accepting more concurrent calls than the provider lets through anyway.
- **The queue wait timeout** — how long a request will wait for a free slot before getting a fast `429` instead of an eventual slow success. Too long and you're back to the unprotected server's problem (everything queues and gets slow together); too short and you reject bursts that would have cleared quickly.

## A real asyncio gotcha this repo hit (and the fix)

Creating `asyncio.Semaphore()` at module level and using it across multiple event loops throws `RuntimeError: <Semaphore ...> is bound to a different event loop`. This is invisible in normal single-process production (one process = one event loop for its whole life) but broke immediately when testing — each pytest test function gets a fresh event loop. The fix, in [`examples/04-load-handling/server.py`](../examples/04-load-handling/server.py): create the semaphore lazily, bound to whatever loop is actually running, and rebuild it if that loop changes. This is the generally-correct pattern for **any** asyncio primitive (Semaphore, Lock, Queue) shared across requests — worth knowing before it surprises you in a different context than "my tests broke."

## Beyond one process: what changes at real scale

Everything in this repo's examples uses **in-memory state** (the semaphore, session/conversation history, rate-limit counters) — correct and simple for one process, and **silently wrong** the moment you run more than one process or instance behind a load balancer, because each process has its own separate memory. A user's second request can land on a different process with no memory of their first one.

What that actually requires, past one process:
- **Shared session/conversation state** — Redis or DynamoDB instead of an in-memory dict, so any instance can serve any user's next request.
- **A distributed rate limiter** — an in-memory sliding window (what `examples/04` and the `aws-migration/terraform/customer-intake` chat agent both use) only limits *that process*; a real multi-instance deployment needs the count shared (Redis is the standard choice here too).
- **The concurrency limit becomes per-instance, not global** — if you run 4 instances each capped at 3 concurrent LLM calls, your actual ceiling is 12, not 3. Either account for that in provider rate-limit math, or move to a shared limiter (a distributed semaphore, or a queue-based worker pool) if you need a true global cap.

## Caching — the highest-leverage optimization for RAG specifically

Going back to [docs/05-rag-pipelines.md](05-rag-pipelines.md): a RAG request is at minimum an embedding call plus a generation call. Caching embeddings for repeated or near-duplicate queries (an exact-match cache, or a semantic cache keyed by embedding similarity above some threshold) cuts both latency and cost for the queries that recur — which in most real applications is a large fraction of traffic (common questions get asked repeatedly).

## Observability is part of load handling, not a separate concern

You can't tune a concurrency limit, a timeout, or a cache TTL without knowing your actual traffic pattern and failure rate — see [docs/08-observability-evaluation.md](08-observability-evaluation.md).
