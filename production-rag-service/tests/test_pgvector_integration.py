"""
The one test file in this suite that needs real infrastructure: a real
Postgres with the pgvector extension (docker-compose.yml in the repo
root brings one up). It's SKIPPED automatically if that Postgres isn't
reachable — the rest of the suite (tests/test_*.py) runs fine without it,
using the in-memory vector store instead (see app/rag/vector_store.py's
docstring for why both exist).

Run it for real:
    docker compose up -d postgres
    pytest tests/test_pgvector_integration.py -v
"""
import asyncio
import os

import pytest

POSTGRES_DSN = os.environ.get("TEST_POSTGRES_DSN", "postgresql://postgres:postgres@localhost:5432/postgres")


def _postgres_reachable() -> bool:
    try:
        import asyncpg
    except ImportError:
        return False

    async def _check():
        try:
            conn = await asyncio.wait_for(asyncpg.connect(POSTGRES_DSN), timeout=2.0)
            await conn.close()
            return True
        except Exception:
            return False

    try:
        return asyncio.run(_check())
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _postgres_reachable(),
    reason=f"No Postgres reachable at {POSTGRES_DSN} — run `docker compose up -d postgres` first.",
)


@pytest.fixture
async def pg_store():
    import asyncpg
    from app.rag.vector_store import PgVectorVectorStore

    pool = await asyncpg.create_pool(POSTGRES_DSN)
    store = PgVectorVectorStore(pool, embedding_dim=8)
    await store.ensure_schema()
    # Clean slate per test — this table is test-only data.
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM chunk_embeddings")
    yield store
    await pool.close()


@pytest.mark.asyncio
async def test_pgvector_add_and_search(pg_store):
    await pg_store.add("c1", "d1", "The cat sat on the mat.", [1, 0.9, 0.1, 0, 0, 0, 0, 0])
    await pg_store.add("c2", "d1", "The dog ran in the park.", [0.9, 1, 0.1, 0, 0, 0, 0, 0])
    await pg_store.add("c3", "d1", "The car needs an oil change.", [0.1, 0.1, 1, 0, 0, 0, 0, 0])

    results = await pg_store.search([1, 1, 0.1, 0, 0, 0, 0, 0], k=3)

    assert len(results) == 3
    assert {results[0].chunk_id, results[1].chunk_id} == {"c1", "c2"}
    assert results[2].chunk_id == "c3"


@pytest.mark.asyncio
async def test_pgvector_upsert_on_conflict(pg_store):
    await pg_store.add("c1", "d1", "original content", [1, 0, 0, 0, 0, 0, 0, 0])
    await pg_store.add("c1", "d1", "updated content", [1, 0, 0, 0, 0, 0, 0, 0])  # same chunk_id

    results = await pg_store.search([1, 0, 0, 0, 0, 0, 0, 0], k=5)
    assert len(results) == 1  # not duplicated
    assert results[0].content == "updated content"
