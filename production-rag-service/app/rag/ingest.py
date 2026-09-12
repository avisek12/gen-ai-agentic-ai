"""
Document ingestion: chunk -> embed -> store, writing both the relational
metadata (app/models.py, via the caller's DB session) and the vector
store entry (app/rag/vector_store.py) for each chunk.
"""
import uuid

from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Document, DocumentChunk
from app.rag.vector_store import VectorStore

# Overlap keeps a fact near a chunk boundary from being split across two
# chunks with neither having full context — see docs/05-rag-pipelines.md
# in the parent repo for why this matters more than embedding model choice.
DEFAULT_CHUNK_SIZE = 500
DEFAULT_CHUNK_OVERLAP = 50


async def ingest_document(
    session: AsyncSession,
    vector_store: VectorStore,
    embeddings,
    source: str,
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> Document:
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    pieces = splitter.split_text(text)

    document = Document(source=source)
    session.add(document)
    await session.flush()  # assigns document.id without committing yet

    if pieces:
        vectors = embeddings.embed_documents(pieces)
        for index, (piece, vector) in enumerate(zip(pieces, vectors)):
            chunk_id = str(uuid.uuid4())
            session.add(DocumentChunk(id=chunk_id, document_id=document.id, chunk_index=index, content=piece))
            await vector_store.add(chunk_id=chunk_id, document_id=document.id, content=piece, embedding=vector)

    await session.commit()
    return document
