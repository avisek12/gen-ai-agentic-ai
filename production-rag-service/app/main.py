"""
Production RAG service: retrieval-grounded chat, streamed over SSE,
protected by a Redis-backed distributed rate limiter and concurrency
semaphore (shared across every instance of this app, unlike the
in-memory versions in the parent repo's examples/04-load-handling),
with durable conversation history in the relational DB instead of
process memory.

Run:
    uvicorn app.main:app --reload
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import select

from app.config import settings
from app.db import get_session, init_db
from app.models import ConversationMessage
from app.rag.chain import build_rag_chain, format_context
from app.rag.embeddings import build_embeddings
from app.rag.ingest import ingest_document
from app.rag.retrieve import retrieve
from app.rag.vector_store import InMemoryVectorStore, VectorStore
from app.rate_limit import DistributedSemaphore, SlidingWindowRateLimiter
from app.redis_client import get_redis

# Module-level singletons, initialized lazily/at startup — see
# examples/04-load-handling/server.py in the parent repo for why
# anything backed by an asyncio primitive should NOT be created at bare
# import time if it might run under more than one event loop (tests vs.
# production). The Redis-backed limiters here don't hold an
# asyncio.Semaphore directly (they hold a Redis client), so they don't
# have that specific problem — but the vector store singleton below is
# still swapped out per-app-instance via the lifespan hook, not reused
# blindly across tests, for the same class of reason (shared mutable
# state should be scoped, not global-by-default).
state: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()

    vector_store: VectorStore
    if settings.vector_store_backend == "pgvector":
        import asyncpg
        from app.rag.vector_store import PgVectorVectorStore

        dsn = settings.database_url.replace("postgresql+asyncpg", "postgresql")
        pool = await asyncpg.create_pool(dsn)
        pg_store = PgVectorVectorStore(pool, settings.embedding_dim)
        await pg_store.ensure_schema()
        vector_store = pg_store
    else:
        vector_store = InMemoryVectorStore()

    redis = get_redis()

    state["vector_store"] = vector_store
    state["embeddings"] = build_embeddings()
    state["rag_chain"] = build_rag_chain()
    state["redis"] = redis
    state["rate_limiter"] = SlidingWindowRateLimiter(
        redis, settings.rate_limit_requests_per_window, settings.rate_limit_window_seconds
    )
    state["llm_semaphore"] = DistributedSemaphore(
        redis, settings.max_concurrent_llm_calls_global, lease_ttl_seconds=30.0
    )

    yield

    if hasattr(state["vector_store"], "pool"):
        await state["vector_store"].pool.close()


app = FastAPI(title="Production RAG Service", lifespan=lifespan)


@app.post("/ingest")
async def ingest_endpoint(source: str, text: str):
    async with get_session() as session:
        document = await ingest_document(session, state["vector_store"], state["embeddings"], source, text)
    return {"document_id": document.id, "source": source}


@app.get("/chat")
async def chat(question: str, session_id: str = Query(..., description="Groups messages into one conversation")):
    if not await state["rate_limiter"].allow(session_id):
        raise HTTPException(status_code=429, detail="Rate limit exceeded for this session — slow down.")

    token = await state["llm_semaphore"].try_acquire("llm-calls")
    if token is None:
        raise HTTPException(status_code=429, detail="Server is at capacity. Try again shortly.")

    async def event_stream():
        try:
            async with get_session() as session:
                session.add(ConversationMessage(session_id=session_id, role="human", content=question))
                await session.commit()

            results = await retrieve(state["vector_store"], state["embeddings"], question, k=4)
            context = format_context(results)

            chunks: list[str] = []
            async for piece in state["rag_chain"].astream({"context": context, "question": question}):
                chunks.append(piece)
                yield f"data: {piece}\n\n"

            async with get_session() as session:
                session.add(ConversationMessage(session_id=session_id, role="ai", content="".join(chunks)))
                await session.commit()

            yield "data: [DONE]\n\n"
        finally:
            await state["llm_semaphore"].release("llm-calls", token)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/history")
async def history(session_id: str):
    async with get_session() as session:
        result = await session.execute(
            select(ConversationMessage)
            .where(ConversationMessage.session_id == session_id)
            .order_by(ConversationMessage.created_at)
        )
        messages = result.scalars().all()
    return [{"role": m.role, "content": m.content, "created_at": m.created_at.isoformat()} for m in messages]


@app.get("/health")
async def health():
    checks = {}

    try:
        async with get_session() as session:
            await session.execute(select(1))
        checks["database"] = "ok"
    except Exception as e:  # noqa: BLE001 — health check reports, doesn't propagate
        checks["database"] = f"error: {e}"

    try:
        await state["redis"].ping()
        checks["redis"] = "ok"
    except Exception as e:  # noqa: BLE001
        checks["redis"] = f"error: {e}"

    healthy = all(v == "ok" for v in checks.values())
    return JSONResponse(status_code=200 if healthy else 503, content=checks)
