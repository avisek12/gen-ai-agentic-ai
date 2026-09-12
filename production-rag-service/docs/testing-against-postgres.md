# Testing Against a Real Postgres + pgvector

Everything in `tests/` except `tests/test_pgvector_integration.py` runs with zero external services. That one file needs a real Postgres with the pgvector extension, because `PgVectorVectorStore` (`app/rag/vector_store.py`) uses pgvector-specific SQL (`<=>` distance operator, `ivfflat` index) that has no in-memory equivalent worth faking — the whole point of that test is proving the *real* SQL is correct.

## Run it

```
docker compose up -d postgres
# wait a few seconds for the healthcheck to pass, or check:
docker compose ps

pip install -r requirements-dev.txt
pytest tests/test_pgvector_integration.py -v
```

Without a reachable Postgres, this file's tests **skip** (not fail) with a clear reason — `pytest tests/` always succeeds regardless of whether Docker is running; you only need this for the two tests that specifically exercise the pgvector backend.

## What these tests actually verify

- `test_pgvector_add_and_search` — the same ranking behavior already proven against `InMemoryVectorStore` in `tests/test_vector_store.py`, now against real pgvector SQL: similar vectors rank above dissimilar ones, using cosine distance (`vector_cosine_ops`).
- `test_pgvector_upsert_on_conflict` — re-ingesting a chunk with the same `chunk_id` updates it in place rather than creating a duplicate row (the `ON CONFLICT ... DO UPDATE` clause in `PgVectorVectorStore.add`).

## If you change `PgVectorVectorStore`

`app/rag/vector_store.py`'s docstring for `PgVectorVectorStore` says it was "reviewed but not yet verified against a live Postgres" at the time this folder was built (no Docker daemon was reachable in that environment). Once you've run these tests successfully once, update that docstring — the "not yet verified" caveat should be a temporary state, not a permanent one.

## Sanity-checking the pgvector image itself

If the tests fail with a connection error rather than skipping, check:
```
docker compose logs postgres
docker compose ps        # healthcheck should show "healthy"
```
The `pgvector/pgvector:pg16` image ships the extension pre-installed — `PgVectorVectorStore.ensure_schema()` still runs `CREATE EXTENSION IF NOT EXISTS vector` itself on first use, so no manual setup should be needed beyond the container being up and healthy.
