# Production RAG Service

A production-shaped RAG chat service: FastAPI, retrieval-grounded generation, a real relational database for durable conversation history, a swappable vector store (in-memory for dev, pgvector for production), and Redis-backed distributed rate limiting/concurrency control — the actual fix for the in-memory-state limitations called out in the parent repo's [`docs/07-load-handling.md`](../docs/07-load-handling.md).

This is a separate, deeper folder from [`../examples/`](../examples/) on purpose: the examples are minimal teaching demos; this is what the same ideas look like once you add a real database, real distributed state, and a real (swappable) vector store.

## Run it

**Zero setup** (SQLite + in-memory vector store + fake LLM/embeddings — everything except Redis):
```
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```
You still need *some* Redis reachable at `REDIS_URL` (default `redis://localhost:6379/0`) for the distributed rate limiter/semaphore — the quickest way: `docker run -p 6379:6379 redis:7-alpine`.

**Full stack** (Postgres+pgvector, Redis, the app, all via Docker):
```
docker compose up -d
```
Then, in another terminal:
```
python scripts/ingest_sample_docs.py
```
and try `GET http://localhost:8000/chat?question=What+is+the+refund+policy%3F&session_id=demo`.

## Test

```
pip install -r requirements-dev.txt
pytest tests/ -v
```
16 tests pass with **zero external services** — `fakeredis` stands in for Redis, SQLite for Postgres, a fake embeddings/chat model for the real LLM API. Two additional tests in `tests/test_pgvector_integration.py` need a real Postgres+pgvector (`docker compose up -d postgres`) and skip automatically, with a clear reason, if one isn't reachable.

## What's actually different from `../examples/04-load-handling`

| | `examples/04-load-handling` | This service |
|---|---|---|
| Concurrency limit | `asyncio.Semaphore`, one process only | Redis-backed, shared across **every instance** |
| Rate limiting | In-memory dict, one process only | Redis sliding-window, shared across every instance |
| Conversation history | In-memory dict (lost on restart) | Relational DB (Postgres in production), durable |
| Retrieval | None — no RAG | Full pipeline: chunk → embed → store → retrieve → ground the answer |
| Vector storage | N/A | Swappable: in-memory (dev) or pgvector (production) behind one interface |

The examples folder's whole point was teaching the *concept* of concurrency limiting in one process. This folder is what "handle full load in production, with more than one instance running" actually requires on top of that concept.

## Structure

```
app/
  config.py          Settings from environment variables
  db.py              Async SQLAlchemy engine/session (SQLite locally, Postgres in production)
  models.py          Relational models: Document, DocumentChunk, ConversationMessage
  redis_client.py    Shared Redis connection
  rate_limit.py      SlidingWindowRateLimiter + DistributedSemaphore (Redis, Lua-script atomic)
  rag/
    vector_store.py  VectorStore interface + InMemoryVectorStore + PgVectorVectorStore
    embeddings.py    Real (OpenAI) or FakeEmbeddings, chosen automatically by config
    ingest.py        Chunk -> embed -> store
    retrieve.py      Embed query -> vector search
    chain.py         Retrieved context + question -> grounded answer (LCEL)
  main.py            FastAPI app wiring all of the above together
tests/               16 tests, zero external services needed; 2 more that need real Postgres
scripts/             Sample doc ingestion + a production load test
docker-compose.yml   Postgres (pgvector image) + Redis + the app
```

## Read next

- [`docs/architecture.md`](docs/architecture.md) — how the pieces fit together and the specific decisions behind each one.
- [`docs/scaling.md`](docs/scaling.md) — sizing the concurrency/rate limits for real traffic, and what changes at real scale.
- [`docs/testing-against-postgres.md`](docs/testing-against-postgres.md) — running the pgvector integration tests for real.
