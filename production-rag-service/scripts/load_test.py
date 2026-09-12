"""
Fires a burst of concurrent chat requests at a REAL running instance of
this service, using distinct session ids so the per-session rate limiter
doesn't confound the results — this measures the GLOBAL concurrency
semaphore's behavior specifically (MAX_CONCURRENT_LLM_CALLS_GLOBAL),
which is meant to hold across every instance of the service, not just
one process.

Run the service first (ideally via docker-compose so Redis/Postgres are
real, not the local single-process fallbacks):
    docker compose up -d
    python scripts/ingest_sample_docs.py
Then:
    python scripts/load_test.py --requests 60
"""
import argparse
import asyncio
import time
import uuid
from collections import Counter

import httpx


async def fire_one(client: httpx.AsyncClient, i: int) -> tuple[int, float]:
    session_id = f"load-test-{uuid.uuid4().hex[:8]}"  # unique per request -> isolates from per-session rate limiting
    start = time.monotonic()
    try:
        async with client.stream(
            "GET", "/chat", params={"question": "What is the refund policy?", "session_id": session_id}
        ) as r:
            async for _ in r.aiter_text():
                pass
            return r.status_code, time.monotonic() - start
    except httpx.HTTPError:
        return -1, time.monotonic() - start


async def main(base_url: str, num_requests: int):
    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
        print(f"Firing {num_requests} concurrent requests (each its own session) at {base_url} ...")
        start = time.monotonic()
        results = await asyncio.gather(*[fire_one(client, i) for i in range(num_requests)])
        elapsed = time.monotonic() - start

        statuses = Counter(status for status, _ in results)
        durations = [d for _, d in results]

        print(f"\nDone in {elapsed:.2f}s")
        print("Status code counts:", dict(statuses))
        print(f"Request duration — min {min(durations):.2f}s, max {max(durations):.2f}s, "
              f"avg {sum(durations)/len(durations):.2f}s")
        print("\n429s here mean the GLOBAL concurrency semaphore (Redis-backed, shared across every "
              "instance of this service) is doing its job — see app/rate_limit.py and docs/scaling.md.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--requests", type=int, default=60)
    args = parser.parse_args()

    asyncio.run(main(f"http://{args.host}:{args.port}", args.requests))
