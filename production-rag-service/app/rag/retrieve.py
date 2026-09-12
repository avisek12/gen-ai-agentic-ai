from app.rag.vector_store import SearchResult, VectorStore


async def retrieve(vector_store: VectorStore, embeddings, query: str, k: int = 4) -> list[SearchResult]:
    query_embedding = embeddings.embed_query(query)
    return await vector_store.search(query_embedding, k=k)
