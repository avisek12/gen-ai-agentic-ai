# 04 — Load Handling

The same streaming chat server as [`03-fullstack-streaming`](../03-fullstack-streaming/), with a concurrency limit and backpressure added — plus a real load test proving the difference, run against both servers live.

## Run it

```
pip install -r requirements.txt
uvicorn server:app --port 8001
```

In another terminal:
```
python load_test.py --port 8001 --requests 60
```

## Test

```
pytest test_server.py -v
```

Tests use `httpx.AsyncClient` against the app directly via `ASGITransport`, firing real concurrent requests with `asyncio.gather` — a sequential test client can't exercise concurrency at all, so this is the part that actually matters here.

## Real results, measured — not illustrative numbers

Run live during development of this example, 60 concurrent requests against each server:

| | Unprotected (`03-fullstack-streaming`) | Protected (this example) |
|---|---|---|
| Status codes | 60× `200` | 21× `200`, 39× `429` |
| Request duration | **every single one** took 2.76–2.83s | successes 0.42–2.16s; rejections near-instant |
| Max concurrent in-flight | uncapped | capped at 3 (the configured limit) |

The unprotected server accepted all 60 and made **every one of them slow** — nobody got a fast answer, because the process was splitting its attention 60 ways. The protected server rejected the requests it couldn't serve promptly (in well under half a second, no multi-second wait for a rejection) and kept the accepted ones within the concurrency limit. Reproduce it yourself: `load_test.py --port 8000` against `03-fullstack-streaming`'s server vs. `--port 8001` against this one.

## The real gotcha this code works around (found by testing, not assumed)

`asyncio.Semaphore()` created once at module import time binds permanently to whichever event loop first uses it. That's invisible in normal single-process production use, but breaks the moment the app runs under more than one event loop — exactly what happens across separate pytest test functions. `server.py`'s `Load.get_semaphore()` creates it lazily against whatever loop is actually running and rebuilds it if that changes. See the comment block at the top of `server.py` for the full explanation — this is a generally-correct pattern for any asyncio primitive shared across requests, not a test-only workaround.

## Sizing the concurrency limit for real use

`MAX_CONCURRENT_LLM_CALLS` here is an arbitrary demo value (3). For real use, size it against:
- **Your LLM provider's actual rate limit** (requests/min and tokens/min) — no point accepting more concurrent calls than the provider will actually let through.
- **Memory per in-flight request** — each one holds conversation state/context in memory for its duration.
- **Your own downstream dependencies** (a vector store, a database) — the LLM call is rarely the only slow thing in a real RAG/agentic request.

See [docs/07-load-handling.md](../../docs/07-load-handling.md) for the fuller picture — this example demonstrates one piece (concurrency + backpressure) of a larger set of concerns (caching, queuing across processes, horizontal scaling).
