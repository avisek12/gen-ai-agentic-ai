"""
Shared fixtures. Everything here runs with zero external services:
fakeredis instead of real Redis, SQLite instead of Postgres, fake
embeddings/chat model instead of a real LLM API. This is what makes the
whole suite runnable with `pytest`, no Docker required — see
docs/testing-against-postgres.md for the separate, marked-slow suite
that needs a real Postgres+pgvector via docker-compose.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fakeredis.aioredis
import pytest
import pytest_asyncio

import app.redis_client as redis_client_module

_fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
redis_client_module.get_redis = lambda: _fake_redis


@pytest.fixture(autouse=True)
def _use_temp_sqlite_db(tmp_path, monkeypatch):
    """Give every test its own throwaway SQLite file so tests don't
    leak state into each other via a shared local.db."""
    db_path = tmp_path / "test.db"
    monkeypatch.setattr("app.config.settings", _settings_with_db_url(f"sqlite+aiosqlite:///{db_path}"))
    # db.py builds its engine from settings at import time, so re-point it
    # for this test's engine/session factory too.
    import app.db as db_module
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    db_module.engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", pool_pre_ping=True)
    db_module.async_session_factory = async_sessionmaker(db_module.engine, expire_on_commit=False)
    yield


def _settings_with_db_url(url: str):
    from dataclasses import replace
    from app.config import settings as base_settings
    return replace(base_settings, database_url=url)


@pytest_asyncio.fixture(autouse=True)
async def _flush_fake_redis():
    """Each test starts with a clean Redis so rate limits/semaphores from
    one test don't bleed into the next."""
    await _fake_redis.flushall()
    yield
