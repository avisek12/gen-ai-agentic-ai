import pytest

from app.db import get_session, init_db
from app.rag.chain import build_rag_chain, format_context
from app.rag.embeddings import FakeEmbeddings
from app.rag.ingest import ingest_document
from app.rag.retrieve import retrieve
from app.rag.vector_store import InMemoryVectorStore


@pytest.mark.asyncio
async def test_ingest_creates_document_and_chunks():
    await init_db()
    vector_store = InMemoryVectorStore()
    embeddings = FakeEmbeddings(dim=32)

    text = "A" * 1200  # long enough to force multiple chunks at the default 500/50 chunk size

    async with get_session() as session:
        document = await ingest_document(session, vector_store, embeddings, source="test.txt", text=text)

    assert document.id
    assert len(vector_store._rows) > 1  # confirms it actually split into multiple chunks


@pytest.mark.asyncio
async def test_retrieve_returns_relevant_chunks():
    await init_db()
    vector_store = InMemoryVectorStore()
    embeddings = FakeEmbeddings(dim=32)

    async with get_session() as session:
        await ingest_document(
            session, vector_store, embeddings, source="policy.txt",
            text="Refunds are available within 30 days of purchase.",
        )

    results = await retrieve(vector_store, embeddings, "refund policy", k=4)
    assert len(results) > 0
    assert "Refunds" in results[0].content


@pytest.mark.asyncio
async def test_full_pipeline_ingest_retrieve_generate():
    await init_db()
    vector_store = InMemoryVectorStore()
    embeddings = FakeEmbeddings(dim=32)
    chain = build_rag_chain()

    async with get_session() as session:
        await ingest_document(
            session, vector_store, embeddings, source="hours.txt",
            text="Support hours are 9am-5pm Eastern, Monday to Friday.",
        )

    results = await retrieve(vector_store, embeddings, "What are your hours?", k=4)
    context = format_context(results)
    answer = chain.invoke({"context": context, "question": "What are your hours?"})

    assert isinstance(answer, str)
    assert len(answer) > 0


@pytest.mark.asyncio
async def test_format_context_handles_empty_results():
    assert format_context([]) == "(no relevant context found)"
