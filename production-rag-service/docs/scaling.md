# Scaling This Service for Real Traffic

## Sizing `MAX_CONCURRENT_LLM_CALLS_GLOBAL`

This is a **global** cap across every instance of the service combined (unlike `examples/04-load-handling`'s per-process limit — see [architecture.md](architecture.md) for why that distinction matters). Size it against:

1. **Your LLM provider's actual rate limit** (requests/min and tokens/min for your account tier) — there's no benefit to accepting more concurrent calls than the provider will let through; you'll just collect provider-side 429s instead of your own.
2. **Memory per in-flight request** — each holds conversation context and retrieved chunks in memory for the request's duration.
3. **Database/Redis connection pool size** — each in-flight request holds a DB connection (for history) and makes Redis round-trips. If `MAX_CONCURRENT_LLM_CALLS_GLOBAL` exceeds your DB pool's `pool_size + max_overflow`, requests will queue on the connection pool instead of the semaphore, defeating the point of controlling admission at the semaphore layer.

Start conservative, watch `/health` and your provider's dashboard, and raise it based on observed behavior — not a guess.

## Sizing the per-session rate limit

`RATE_LIMIT_REQUESTS_PER_WINDOW` / `RATE_LIMIT_WINDOW_SECONDS` protect against one session monopolizing capacity, not against overall load (that's the semaphore's job). A legitimate interactive chat user rarely sends more than a handful of messages per minute — size this against real observed usage patterns, generous enough that no genuine user notices it, tight enough that a runaway client (a bug, a bot, an abusive script) can't starve everyone else.

## Horizontal scaling: what's already handled vs. what isn't

**Already handled by this service's design:**
- Rate limiting and concurrency control (Redis-backed, correct across any number of instances — this is the entire point of this folder vs. `examples/04`).
- Conversation history (in the shared database, not process memory).
- Vector search (pgvector in Postgres, shared, not per-process).

**Still your responsibility when you actually deploy multiple instances:**
- **A load balancer** in front of the instances (round-robin is fine — nothing here requires session affinity/sticky sessions, since all shared state lives in Redis/Postgres, not in-process).
- **Database connection pool sizing across instances** — if you run 5 instances each with `pool_size=10`, your database sees up to 50 concurrent connections; make sure Postgres's own `max_connections` accommodates that (or put a connection pooler like PgBouncer in front of it).
- **Redis itself becoming a bottleneck or single point of failure at very high scale** — a single Redis instance handles a large volume of these lightweight sorted-set operations, but at real high scale, look at Redis Cluster or a managed Redis service with its own HA story. This service's `redis_client.py` doesn't assume anything cluster-incompatible, but it also doesn't configure cluster mode — that's an infrastructure decision, not a code change.

## Caching — the optimization this service doesn't yet implement

`app/config.py` already has `RESPONSE_CACHE_TTL_SECONDS` defined but unused — the natural next addition. For repeated or near-duplicate questions (common in real traffic — the same FAQ-style question asked by many users), caching either the embedding or the final answer (keyed by a normalized question, or by embedding-similarity above some threshold) avoids redundant LLM/embedding calls entirely. This is the single highest-leverage optimization available once you have real traffic data showing which questions actually repeat.

## What changes if this becomes agentic (tool calls, multi-step reasoning)

Everything in [`docs/04-agentic-patterns.md`](../../docs/04-agentic-patterns.md) applies once this stops being a single retrieve-then-generate flow — plan for more LLM calls per user request (each reasoning step is its own call), which directly multiplies load against the same `MAX_CONCURRENT_LLM_CALLS_GLOBAL` budget. A single "simple" chat request costing 1 LLM call today could cost 3-5 as an agentic loop tomorrow — resize the concurrency limit accordingly when that happens, don't assume it stays valid.
