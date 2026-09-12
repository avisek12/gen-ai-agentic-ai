# 03 — Full-Stack Streaming

A FastAPI backend streaming an LLM's response to the browser token-by-token over Server-Sent Events (SSE), plus a minimal HTML frontend that consumes it with `EventSource`.

## Run it for real (in a browser)

```
pip install -r requirements.txt
uvicorn server:app --reload
```
Open `http://127.0.0.1:8000/` and ask a question — watch the answer appear incrementally rather than all at once.

## Test

```
pytest test_server.py -v
```

## Why SSE and not just returning the full response

Without streaming, the browser waits for the *entire* LLM response before showing anything — for a multi-paragraph answer that can be several seconds of a blank screen. Streaming shows the first tokens almost immediately, which is the single biggest perceived-latency improvement available for a chat UI, and it's nearly free here: `chain.astream(...)` already works because every piece of the LCEL chain supports streaming (see [docs/02-langchain-basics.md](../../docs/02-langchain-basics.md)).

**SSE vs. WebSockets** — this example uses SSE because it's simpler (plain HTTP, no separate protocol, works through most proxies/load balancers without special config) and the data only flows one direction (server → browser), which is all a streamed answer needs. Reach for WebSockets instead when you need bidirectional communication — e.g., the user can interrupt/redirect the model mid-response.

## What this example does *not* yet handle

Nothing here limits how many of these streaming requests can run at once, or what happens when a burst of users hits it simultaneously. That's the entire subject of [`04-load-handling/`](../04-load-handling/) — the same server, with concurrency limits, a queue, and backpressure added, plus a load test that proves the difference.
