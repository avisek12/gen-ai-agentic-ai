"""
Async SQLAlchemy engine/session — one engine per process, reused across
requests via connection pooling (never open a new connection per
request; that's a common, expensive mistake under load).
"""
from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models import Base

# SQLite's async driver (aiosqlite) uses NullPool and rejects Postgres-only
# pooling kwargs (pool_size/max_overflow/pool_timeout) outright — found by
# actually running this against sqlite, not assumed. Real connection
# pooling only applies (and only matters) once you're on Postgres in
# production; SQLite here is for local dev/tests where pooling is moot.
_engine_kwargs = {"pool_pre_ping": True}
if not settings.database_url.startswith("sqlite"):
    _engine_kwargs.update(
        pool_size=10,      # steady-state connections kept open
        max_overflow=10,   # extra connections allowed during a burst
        pool_timeout=5,    # fail fast (5s) rather than hang if the pool is exhausted
    )

engine = create_async_engine(settings.database_url, **_engine_kwargs)

async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def init_db() -> None:
    """Creates tables if they don't exist. Fine for local dev/tests;
    a real production deployment should use a migration tool (Alembic)
    instead of relying on create_all, so schema changes are tracked and
    reversible."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    async with async_session_factory() as session:
        yield session
