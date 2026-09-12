"""
Distributed load controls backed by Redis — the production replacement
for examples/04-load-handling's in-memory asyncio.Semaphore and
sliding-window dict. Those are correct for exactly one process; the
moment you run more than one instance behind a load balancer, in-memory
state can't see what other instances are doing. Both primitives here use
a Redis sorted set as a "leased slot" registry so state is shared across
every instance talking to the same Redis:

- SlidingWindowRateLimiter — per-key (e.g. per user/session/IP) request
  count over a rolling time window.
- DistributedSemaphore — a global cap on concurrent operations (e.g. LLM
  calls) across ALL instances combined, with automatic lease expiry so a
  crashed process (one that acquired a slot and died before releasing it)
  doesn't permanently leak a slot — a real gotcha with the naive
  INCR/DECR version of this pattern that a lot of examples skip.

Both use a Lua script so the check-and-update is atomic on the Redis
server — without that, two concurrent requests could both read "count is
under the limit" before either writes its own entry, letting the limit
be exceeded (a classic check-then-act race condition).
"""
import time
import uuid

from redis.asyncio import Redis

_LUA_TRY_ACQUIRE = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window_or_ttl = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local token = ARGV[4]

redis.call('ZREMRANGEBYSCORE', key, '-inf', now - window_or_ttl)
local count = redis.call('ZCARD', key)
if count < limit then
    redis.call('ZADD', key, now, token)
    redis.call('EXPIRE', key, math.ceil(window_or_ttl))
    return 1
else
    return 0
end
"""

_LUA_RELEASE = """
redis.call('ZREM', KEYS[1], ARGV[1])
return 1
"""


class SlidingWindowRateLimiter:
    """`await limiter.allow(f"user:{user_id}")` -> True/False. No release
    needed — entries expire out of the window on their own."""

    def __init__(self, redis: Redis, limit: int, window_seconds: int, key_prefix: str = "ratelimit"):
        self.redis = redis
        self.limit = limit
        self.window_seconds = window_seconds
        self.key_prefix = key_prefix
        self._script = redis.register_script(_LUA_TRY_ACQUIRE)

    async def allow(self, identifier: str) -> bool:
        key = f"{self.key_prefix}:{identifier}"
        token = f"{time.time()}-{uuid.uuid4().hex[:8]}"
        result = await self._script(
            keys=[key], args=[time.time(), self.window_seconds, self.limit, token]
        )
        return bool(result)


class DistributedSemaphore:
    """A concurrency cap shared across every process using the same Redis
    key. Use as an async context manager:

        async with semaphore.acquire_or_raise("llm-calls"):
            ... do the limited work ...

    Leases expire after `lease_ttl_seconds` even if never explicitly
    released (e.g. the process crashed) — set this comfortably above your
    slowest expected operation, not exactly at it."""

    def __init__(self, redis: Redis, limit: int, lease_ttl_seconds: float = 30.0, key_prefix: str = "semaphore"):
        self.redis = redis
        self.limit = limit
        self.lease_ttl_seconds = lease_ttl_seconds
        self.key_prefix = key_prefix
        self._acquire_script = redis.register_script(_LUA_TRY_ACQUIRE)
        self._release_script = redis.register_script(_LUA_RELEASE)

    async def try_acquire(self, name: str) -> str | None:
        """Returns a lease token if acquired, None if at capacity."""
        key = f"{self.key_prefix}:{name}"
        token = uuid.uuid4().hex
        acquired = await self._acquire_script(
            keys=[key], args=[time.time(), self.lease_ttl_seconds, self.limit, token]
        )
        return token if acquired else None

    async def release(self, name: str, token: str) -> None:
        key = f"{self.key_prefix}:{name}"
        await self._release_script(keys=[key], args=[token])

    def acquire_or_raise(self, name: str):
        return _SemaphoreLease(self, name)


class SemaphoreAtCapacity(Exception):
    pass


class _SemaphoreLease:
    def __init__(self, semaphore: DistributedSemaphore, name: str):
        self.semaphore = semaphore
        self.name = name
        self.token: str | None = None

    async def __aenter__(self):
        self.token = await self.semaphore.try_acquire(self.name)
        if self.token is None:
            raise SemaphoreAtCapacity(f"'{self.name}' is at its concurrency limit ({self.semaphore.limit})")
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self.token is not None:
            await self.semaphore.release(self.name, self.token)
