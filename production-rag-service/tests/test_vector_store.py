import pytest

from app.rag.vector_store import InMemoryVectorStore


@pytest.mark.asyncio
async def test_ranks_similar_vectors_above_dissimilar():
    store = InMemoryVectorStore()
    await store.add("c1", "d1", "The cat sat on the mat.", [1.0, 0.9, 0.1])
    await store.add("c2", "d1", "The dog ran in the park.", [0.9, 1.0, 0.1])
    await store.add("c3", "d1", "The car needs an oil change.", [0.1, 0.1, 1.0])

    results = await store.search([1.0, 1.0, 0.1], k=3)

    assert {results[0].chunk_id, results[1].chunk_id} == {"c1", "c2"}
    assert results[2].chunk_id == "c3"
    assert results[0].score > results[2].score


@pytest.mark.asyncio
async def test_k_limits_result_count():
    store = InMemoryVectorStore()
    for i in range(10):
        await store.add(f"c{i}", "d1", f"chunk {i}", [float(i), 0.0, 0.0])

    results = await store.search([5.0, 0.0, 0.0], k=3)
    assert len(results) == 3


@pytest.mark.asyncio
async def test_empty_store_returns_empty_list():
    store = InMemoryVectorStore()
    assert await store.search([1.0, 0.0, 0.0]) == []
