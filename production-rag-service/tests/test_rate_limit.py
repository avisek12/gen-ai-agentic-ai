import asyncio

import fakeredis.aioredis
import pytest

from app.rate_limit import DistributedSemaphore, SemaphoreAtCapacity, SlidingWindowRateLimiter


@pytest.mark.asyncio
async def test_sliding_window_rate_limiter_caps_requests():
    r = fakeredis.aioredis.FakeRedis(decode_responses=True)
    limiter = SlidingWindowRateLimiter(r, limit=3, window_seconds=60)

    results = [await limiter.allow("user-1") for _ in range(5)]
    assert results == [True, True, True, False, False]


@pytest.mark.asyncio
async def test_sliding_window_rate_limiter_isolates_identifiers():
    r = fakeredis.aioredis.FakeRedis(decode_responses=True)
    limiter = SlidingWindowRateLimiter(r, limit=1, window_seconds=60)

    assert await limiter.allow("user-a") is True
    assert await limiter.allow("user-a") is False
    assert await limiter.allow("user-b") is True  # separate bucket


@pytest.mark.asyncio
async def test_distributed_semaphore_caps_real_concurrency():
    """The important test: fires real concurrent workers via
    asyncio.gather, not sequential calls, and proves the atomic Lua
    script actually prevents the limit from being exceeded."""
    r = fakeredis.aioredis.FakeRedis(decode_responses=True)
    sem = DistributedSemaphore(r, limit=3, lease_ttl_seconds=10)

    concurrent = 0
    max_concurrent = 0
    rejected = 0
    lock = asyncio.Lock()

    async def worker():
        nonlocal concurrent, max_concurrent, rejected
        try:
            async with sem.acquire_or_raise("test-op"):
                async with lock:
                    concurrent += 1
                    max_concurrent = max(max_concurrent, concurrent)
                await asyncio.sleep(0.05)
                async with lock:
                    concurrent -= 1
        except SemaphoreAtCapacity:
            rejected += 1

    await asyncio.gather(*[worker() for _ in range(20)])

    assert max_concurrent <= 3
    assert rejected > 0


@pytest.mark.asyncio
async def test_semaphore_release_frees_the_slot():
    r = fakeredis.aioredis.FakeRedis(decode_responses=True)
    sem = DistributedSemaphore(r, limit=1, lease_ttl_seconds=10)

    async with sem.acquire_or_raise("solo"):
        assert await sem.try_acquire("solo") is None  # at capacity while held

    token = await sem.try_acquire("solo")  # freed after the `async with` released it
    assert token is not None
    await sem.release("solo", token)
