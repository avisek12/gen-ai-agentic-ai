"""
Vector storage behind a swappable interface: `InMemoryVectorStore` for
local dev/tests (zero extra infrastructure, pure Python), and
`PgVectorVectorStore` for production (a real Postgres instance with the
pgvector extension — persistent, shared across every app instance, and
capable of indexed similarity search at real scale).

Swapping backends never touches ingest.py, retrieve.py, or chain.py —
they only depend on this interface. Select which one via
config.VECTOR_STORE_BACKEND ("memory" | "pgvector").
"""
from __future__ import annotations

import abc
from dataclasses import dataclass

import numpy as np


@dataclass
class SearchResult:
    chunk_id: str
    content: str
    document_id: str
    score: float  # cosine similarity, higher = more similar


class VectorStore(abc.ABC):
    @abc.abstractmethod
    async def add(self, chunk_id: str, document_id: str, content: str, embedding: list[float]) -> None: ...

    @abc.abstractmethod
    async def search(self, query_embedding: list[float], k: int = 4) -> list[SearchResult]: ...


class InMemoryVectorStore(VectorStore):
    """Pure-Python cosine similarity over an in-process list. No external
    dependency, resets on restart, not shared across processes — correct
    tool for local development and fast tests, wrong tool for production
    (see PgVectorVectorStore for that)."""

    def __init__(self):
        self._rows: list[tuple[str, str, str, np.ndarray]] = []  # (chunk_id, document_id, content, vector)

    async def add(self, chunk_id: str, document_id: str, content: str, embedding: list[float]) -> None:
        vec = np.array(embedding, dtype=np.float32)
        self._rows.append((chunk_id, document_id, content, vec))

    async def search(self, query_embedding: list[float], k: int = 4) -> list[SearchResult]:
        if not self._rows:
            return []
        query = np.array(query_embedding, dtype=np.float32)
        query_norm = np.linalg.norm(query) or 1e-8

        scored = []
        for chunk_id, document_id, content, vec in self._rows:
            vec_norm = np.linalg.norm(vec) or 1e-8
            similarity = float(np.dot(query, vec) / (query_norm * vec_norm))
            scored.append(SearchResult(chunk_id, content, document_id, similarity))

        scored.sort(key=lambda r: r.score, reverse=True)
        return scored[:k]


class PgVectorVectorStore(VectorStore):
    """Production backend: Postgres + the pgvector extension. Manages its
    own table (separate from the SQLAlchemy ORM models in app/models.py —
    see that file's docstring for why) via raw parameterized SQL, since
    pgvector's `<->` distance operator and index types are Postgres-
    specific and this keeps that clearly isolated to one file.

    NOT YET VERIFIED AGAINST A LIVE POSTGRES in this environment (no
    running Postgres+pgvector instance was available while this was
    built — see ../docker-compose.yml and ../docs/testing-against-postgres.md
    for how to actually validate this once you have Docker/Postgres
    running). The SQL matches documented pgvector usage; treat it as
    reviewed-but-unverified until you've run it for real.
    """

    def __init__(self, asyncpg_pool, embedding_dim: int):
        self.pool = asyncpg_pool
        self.embedding_dim = embedding_dim

    async def ensure_schema(self) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            await conn.execute(f"""
                CREATE TABLE IF NOT EXISTS chunk_embeddings (
                    chunk_id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    embedding VECTOR({self.embedding_dim}) NOT NULL
                )
            """)
            # IVFFlat index for approximate nearest-neighbor search at
            # scale — exact search (no index) is fine up to a few thousand
            # rows; past that, an index trades a little accuracy for a lot
            # of speed. `lists` should be roughly sqrt(row_count) per
            # pgvector's own guidance — tune once you know your real data size.
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS chunk_embeddings_embedding_idx
                ON chunk_embeddings USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 100)
            """)

    async def add(self, chunk_id: str, document_id: str, content: str, embedding: list[float]) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO chunk_embeddings (chunk_id, document_id, content, embedding)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (chunk_id) DO UPDATE
                    SET content = EXCLUDED.content, embedding = EXCLUDED.embedding
                """,
                chunk_id, document_id, content, str(embedding),
            )

    async def search(self, query_embedding: list[float], k: int = 4) -> list[SearchResult]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT chunk_id, document_id, content, 1 - (embedding <=> $1) AS score
                FROM chunk_embeddings
                ORDER BY embedding <=> $1
                LIMIT $2
                """,
                str(query_embedding), k,
            )
        return [SearchResult(r["chunk_id"], r["content"], r["document_id"], float(r["score"])) for r in rows]
