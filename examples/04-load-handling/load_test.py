"""
Fires a burst of concurrent requests at a REALLY RUNNING server (not the
in-process ASGI transport the pytest suite uses) and reports what
happened — status code counts, timing, and the server's own reported
concurrency high-water mark via /stats.

Run the server first, in another terminal:
    uvicorn server:app --port 8001

Then:
    python load_test.py                  # against this repo's protected server (port 8001)
    python load_test.py --port 8000      # try it against ../03-fullstack-streaming's
                                          # UNPROTECTED server instead, for comparison
                                          # (start it with: uvicorn server:app --port 8000
                                          # from examples/03-fullstack-streaming/)
"""
import argparse
import asyncio
import time
from collections import Counter

import httpx


async def fire_one(client: httpx.AsyncClient, i: int) -> tuple[int, float]:
    start = time.monotonic()
    try:
        async with client.stream("GET", "/chat", params={"question": f"load-test-{i}"}) as r:
            async for _ in r.aiter_text():
                pass
            return r.status_code, time.monotonic() - start
    except httpx.HTTPError as e:
        return -1, time.monotonic() - start


async def main(base_url: str, num_requests: int):
    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
        print(f"Firing {num_requests} concurrent requests at {base_url} ...")
        start = time.monotonic()
        results = await asyncio.gather(*[fire_one(client, i) for i in range(num_requests)])
        elapsed = time.monotonic() - start

        statuses = Counter(status for status, _ in results)
        durations = [d for _, d in results]

        print(f"\nDone in {elapsed:.2f}s")
        print("Status code counts:", dict(statuses))
        print(f"Request duration — min {min(durations):.2f}s, max {max(durations):.2f}s, "
              f"avg {sum(durations)/len(durations):.2f}s")

        try:
            stats = (await client.get("/stats")).json()
            print("Server-reported stats:", stats)
        except httpx.HTTPError:
            pass  # /stats only exists on this repo's own server, not a real target


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--requests", type=int, default=60)
    args = parser.parse_args()

    asyncio.run(main(f"http://{args.host}:{args.port}", args.requests))
