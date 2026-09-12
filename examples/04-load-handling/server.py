"""
The same streaming chat server as ../03-fullstack-streaming/, now with the
two things that example is missing: a concurrency limit and backpressure.

Why this matters specifically for LLM-backed APIs (not just "web apps in
general"): a single LLM call ties up a connection for seconds, not
milliseconds. A normal web app's requests finish fast enough that a burst
of traffic mostly just queues briefly; an LLM app's requests are slow
enough that an unbounded burst can pile up hundreds of multi-second
in-flight calls, exhausting memory/connections and making *every* request
slow, including ones that would otherwise have been fast. Capping
concurrency and rejecting fast (429) past that cap keeps the requests you
DO accept fast, instead of accepting everything and making all of them slow.

A real gotcha this file works around, found by testing (not assumed):
`asyncio.Semaphore()` created once at import time gets permanently bound
to whichever event loop first touches it. That's invisible in normal
single-process production use (one process, one event loop, for the
process's whole life) but breaks the moment something runs the app under
more than one event loop — which is exactly what happens across separate
test functions. `Load.get_semaphore()` below creates it lazily, bound to
whatever loop is *actually* running right now, and recreates it if that
loop ever changes. This is the generally-correct pattern for any asyncio
primitive (Semaphore/Lock/Queue) shared across requests, not just a
test workaround.

Run:
    uvicorn server:app --reload
Load-test it:
    python load_test.py
"""
import asyncio

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

app = FastAPI(title="Load-Handling Demo")

# How many LLM calls this process will run at the same time. Size this
# against your actual LLM provider's rate limit and your own memory/CPU,
# not an arbitrary number — see docs/07-load-handling.md.
MAX_CONCURRENT_LLM_CALLS = 3

# How long an incoming request will wait for a free slot before this
# process gives up and returns 429, instead of queuing forever.
QUEUE_WAIT_TIMEOUT_SECONDS = 2.0


class Load:
    """Holds the concurrency-limiting state, created lazily against
    whichever event loop is actually running (see module docstring)."""
    semaphore: asyncio.Semaphore | None = None
    loop: asyncio.AbstractEventLoop | None = None
    in_flight_count: int = 0
    max_observed_in_flight: int = 0

    @classmethod
    def get_semaphore(cls) -> asyncio.Semaphore:
        loop = asyncio.get_running_loop()
        if cls.semaphore is None or cls.loop is not loop:
            cls.semaphore = asyncio.Semaphore(MAX_CONCURRENT_LLM_CALLS)
            cls.loop = loop
            cls.in_flight_count = 0
            cls.max_observed_in_flight = 0
        return cls.semaphore


def build_chain():
    prompt = ChatPromptTemplate.from_messages([("human", "{question}")])
    # A slow fake model, on purpose — makes the concurrency limit visible
    # in a load test without needing a real (slow, costly) LLM call.
    model = FakeListChatModel(responses=["Handled without overloading the server."])
    return prompt | model | StrOutputParser()


chain = build_chain()


@app.get("/chat")
async def chat(question: str):
    semaphore = Load.get_semaphore()
    try:
        await asyncio.wait_for(semaphore.acquire(), timeout=QUEUE_WAIT_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=429,
            detail=f"Server is at capacity ({MAX_CONCURRENT_LLM_CALLS} concurrent requests). Try again shortly.",
        )

    async def event_stream():
        Load.in_flight_count += 1
        Load.max_observed_in_flight = max(Load.max_observed_in_flight, Load.in_flight_count)
        try:
            # Simulate real LLM latency so a load test can actually observe
            # requests overlapping in time, not completing instantly.
            await asyncio.sleep(0.2)
            async for chunk in chain.astream({"question": question}):
                yield f"data: {chunk}\n\n"
            yield "data: [DONE]\n\n"
        finally:
            Load.in_flight_count -= 1
            semaphore.release()

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/stats")
async def stats():
    """Not something you'd expose publicly as-is — useful here to make the
    concurrency behavior observable in the load test and tests."""
    return {
        "in_flight": Load.in_flight_count,
        "max_observed_in_flight": Load.max_observed_in_flight,
        "limit": MAX_CONCURRENT_LLM_CALLS,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001)
