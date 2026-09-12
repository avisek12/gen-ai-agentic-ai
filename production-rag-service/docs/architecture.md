# Architecture

## Request flow: `GET /chat?question=...&session_id=...`

```
1. SlidingWindowRateLimiter.allow(session_id)   -> 429 if this session is over its rate limit
2. DistributedSemaphore.try_acquire("llm-calls") -> 429 if the whole service is at capacity
3. Persist the human message to the DB (ConversationMessage)
4. embeddings.embed_query(question)
5. vector_store.search(query_embedding, k=4)     -> relevant chunks
6. rag_chain.astream({context, question})        -> stream tokens back over SSE
7. Persist the full AI message to the DB
8. Release the semaphore lease
```

Steps 1-2 are cheap, fast checks that happen *before* any expensive work — the whole point of backpressure is rejecting what you can't serve promptly without making it wait to find that out (see the parent repo's [`docs/07-load-handling.md`](../../docs/07-load-handling.md) for the measured evidence this matters).

## Why two separate limiters, not one

- **`SlidingWindowRateLimiter`** is *per-identifier* (here, per `session_id`) — it stops one user from monopolizing the service, independent of overall load.
- **`DistributedSemaphore`** is *global* — it caps how many LLM calls run at once across the **entire service**, independent of who's asking. Sized against your actual LLM provider's rate limit (see [scaling.md](scaling.md)).

A single user hammering `/chat` hits the rate limiter first; a legitimate burst of many different users hits the semaphore. You need both — one doesn't substitute for the other.

## Why Redis for both, not in-memory

Both limiters need to see the same state from every process/instance of this service. An in-memory `asyncio.Semaphore` (what `examples/04-load-handling` uses) only knows about requests in its own process — run two instances behind a load balancer and each thinks it has the full concurrency budget to itself, doubling your real limit without meaning to. Redis is the shared source of truth every instance reads and writes.

## Why a Lua script for the atomic check-and-update

```lua
redis.call('ZREMRANGEBYSCORE', key, '-inf', now - ttl)
local count = redis.call('ZCARD', key)
if count < limit then
    redis.call('ZADD', key, now, token)
    ...
```

Without running this as one atomic script on the Redis server, two concurrent requests could both read "count is under the limit" via separate round-trips before either writes its own entry — a classic check-then-act race that would let the limit be exceeded under real concurrency. `tests/test_rate_limit.py::test_distributed_semaphore_caps_real_concurrency` proves this holds under 20 real concurrent `asyncio.gather`'d requests, not just sequential calls.

## Why leases expire (TTL) instead of a plain counter

A naive `INCR`/`DECR` semaphore leaks a slot forever if the process holding it crashes before decrementing. Here, each acquired slot is a sorted-set entry with a timestamp; every acquire attempt first purges entries older than the lease TTL. A crashed process's slot frees itself automatically once the TTL elapses — no manual cleanup, no permanently "stuck" capacity.

## Why the vector store is an abstraction, not just "use pgvector"

`app/rag/vector_store.py` defines one interface (`add`, `search`) with two implementations. `InMemoryVectorStore` needs zero infrastructure and is what every test in `tests/` (except the pgvector-specific ones) runs against — fast, deterministic, no Docker required. `PgVectorVectorStore` is the real production backend: persistent, shared across instances, indexed for approximate nearest-neighbor search at scale. Nothing in `ingest.py`, `retrieve.py`, or `chain.py` knows or cares which one is active — `app/config.py`'s `VECTOR_STORE_BACKEND` picks it at startup.

## Why conversation history is a database table, not a LangGraph checkpointer

The parent repo's [`docs/03-langgraph-basics.md`](../../docs/03-langgraph-basics.md) covers LangGraph's checkpointer as the current recommended pattern for conversational state — and it's a good one. This service uses a plain relational table instead because conversation history here needs to be queryable independent of any particular graph run (the `/history` endpoint is a simple `SELECT`), and because it's meant to demonstrate the "durable state in a real database" pattern explicitly, since that's the production gap this whole folder exists to close. In a LangGraph-based agentic version of this service, a Postgres-backed checkpointer (`langgraph.checkpoint.postgres`) would be the more idiomatic choice — worth building as a follow-up if this service grows agentic behavior (tool calls, multi-step reasoning) rather than staying a single retrieve-then-generate flow.

## Connection pooling

`app/db.py` configures `pool_size`/`max_overflow`/`pool_timeout` for Postgres — but **not** for SQLite, whose async driver uses `NullPool` and rejects those arguments outright (a real error hit and fixed while building this, not a hypothetical). Pooling only matters once you're on Postgres in production; SQLite here is for local dev/tests where it's moot.
