"""
All configuration comes from environment variables, with sensible local
defaults — nothing here is meant to be edited in code between dev and
production; only the environment changes.
"""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    # Relational store: conversation history, document metadata. SQLite
    # locally (zero setup), Postgres in production (set DATABASE_URL).
    # Async drivers only — sqlite+aiosqlite / postgresql+asyncpg.
    database_url: str = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./local.db")

    # Vector store backend: "memory" (no dependencies, process-local, for
    # local dev/tests) or "pgvector" (production — requires DATABASE_URL
    # to point at a Postgres instance with the pgvector extension).
    vector_store_backend: str = os.environ.get("VECTOR_STORE_BACKEND", "memory")
    embedding_dim: int = int(os.environ.get("EMBEDDING_DIM", "1536"))  # text-embedding-3-small

    redis_url: str = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

    openai_api_key: str | None = os.environ.get("OPENAI_API_KEY")
    chat_model: str = os.environ.get("CHAT_MODEL", "gpt-4o-mini")
    embedding_model: str = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")

    # Distributed load controls — see docs/scaling.md for how to size these.
    max_concurrent_llm_calls_global: int = int(os.environ.get("MAX_CONCURRENT_LLM_CALLS_GLOBAL", "20"))
    concurrency_wait_timeout_seconds: float = float(os.environ.get("CONCURRENCY_WAIT_TIMEOUT_SECONDS", "3.0"))
    rate_limit_requests_per_window: int = int(os.environ.get("RATE_LIMIT_REQUESTS_PER_WINDOW", "30"))
    rate_limit_window_seconds: int = int(os.environ.get("RATE_LIMIT_WINDOW_SECONDS", "60"))

    response_cache_ttl_seconds: int = int(os.environ.get("RESPONSE_CACHE_TTL_SECONDS", "3600"))


settings = Settings()
