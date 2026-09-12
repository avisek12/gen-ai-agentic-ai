"""
Tests real concurrent behavior using httpx.AsyncClient against the ASGI
app directly (no real network/socket needed) — asyncio.gather actually
overlaps the requests in time, unlike sequential TestClient calls, which
is required to observe the concurrency limit doing anything.
"""
import asyncio

import httpx
import pytest

import server


@pytest.fixture(autouse=True)
def reset_counters():
    # Force Load.get_semaphore() to rebuild against this test's event loop
    # and reset counters — see server.py's module docstring for why.
    server.Load.semaphore = None
    server.Load.loop = None
    server.Load.in_flight_count = 0
    server.Load.max_observed_in_flight = 0
    yield


async def _fire(client: httpx.AsyncClient, question: str) -> int:
    async with client.stream("GET", "/chat", params={"question": question}) as r:
        if r.status_code == 200:
            async for _ in r.aiter_text():
                pass
        return r.status_code


@pytest.mark.asyncio
async def test_concurrency_never_exceeds_limit():
    transport = httpx.ASGITransport(app=server.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # A modest burst that comfortably fits within the queue timeout.
        results = await asyncio.gather(*[_fire(client, f"q{i}") for i in range(9)])

    assert all(status == 200 for status in results)
    assert server.Load.max_observed_in_flight <= server.MAX_CONCURRENT_LLM_CALLS


@pytest.mark.asyncio
async def test_large_burst_triggers_backpressure():
    transport = httpx.ASGITransport(app=server.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Far more requests than (limit) can drain within the queue
        # timeout at ~0.2s of simulated work each -> some must get 429
        # instead of queuing indefinitely.
        results = await asyncio.gather(*[_fire(client, f"q{i}") for i in range(60)])

    assert 429 in results, "expected at least one request to be rejected under a large burst"
    assert 200 in results, "expected at least one request to still succeed"
    assert server.Load.max_observed_in_flight <= server.MAX_CONCURRENT_LLM_CALLS


@pytest.mark.asyncio
async def test_stats_endpoint_reports_limit():
    transport = httpx.ASGITransport(app=server.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/stats")
    assert r.status_code == 200
    assert r.json()["limit"] == server.MAX_CONCURRENT_LLM_CALLS
