"""
Embeddings provider. Real embeddings (OpenAI) when OPENAI_API_KEY is
set; a deterministic, dependency-free fake otherwise, so ingest/retrieve
plumbing is testable with zero API cost and zero network calls.

Important: FakeEmbeddings is deterministic (same text -> same vector)
but NOT semantically meaningful — unrelated sentences don't cluster
together the way real embeddings would. It's good for testing that
ingestion and retrieval are wired correctly; it is not a substitute for
testing retrieval QUALITY, which needs real embeddings or hand-crafted
vectors (see tests/test_vector_store.py for the latter).
"""
import hashlib

import numpy as np

from app.config import settings


class FakeEmbeddings:
    def __init__(self, dim: int = 1536):
        self.dim = dim

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed_one(text)

    def _embed_one(self, text: str) -> list[float]:
        seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16) % (2**32)
        rng = np.random.default_rng(seed)
        return rng.normal(size=self.dim).tolist()


def build_embeddings():
    if settings.openai_api_key:
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(model=settings.embedding_model)
    return FakeEmbeddings(dim=settings.embedding_dim)
