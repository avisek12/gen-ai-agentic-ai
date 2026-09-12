# RAG Pipelines

Retrieval-Augmented Generation: get relevant text into the prompt at request time, instead of relying on what the model memorized during training. Builds on the embeddings concept from [docs/01](01-genai-fundamentals.md).

## The pipeline, end to end

1. **Chunk** your source documents into pieces small enough to be individually relevant (too large and a chunk mixes unrelated content, diluting the match; too small and you lose context within a chunk).
2. **Embed** each chunk once, store the vector + the original text (and metadata — source, page, date) in a vector store.
3. At query time, **embed the user's question** with the same embedding model, and retrieve the top-K most similar chunks.
4. **Stuff those chunks into the prompt** alongside the question, and let the model generate an answer grounded in them.

```python
# Retrieval step, conceptually — chain it into an LCEL pipeline like docs/02:
retriever = vector_store.as_retriever(search_kwargs={"k": 4})
chain = (
    {"context": retriever, "question": RunnablePassthrough()}
    | prompt
    | model
    | StrOutputParser()
)
```

## Chunking strategy matters more than model choice

A bad chunking strategy (e.g., fixed 500-character splits with no regard for sentence/paragraph boundaries) produces chunks that cut off mid-thought, which produces retrieval that finds the wrong context even when the embedding model is excellent. Prefer splitters that respect structure (`RecursiveCharacterTextSplitter` splits on paragraph → sentence → word boundaries, in that order) and keep some overlap between consecutive chunks (so a fact near a chunk boundary isn't split across two chunks with neither having full context).

## Failure modes that actually happen in production

- **Retrieval finds semantically similar but factually wrong chunks.** Embeddings measure similarity, not correctness — a chunk about "Q3 2023 revenue" and one about "Q3 2024 revenue" are highly similar and easy to conflate if metadata filtering isn't used to pin down the right time period.
- **The answer cites nothing, or cites the wrong chunk.** Always instruct the model to only answer from provided context and to say so when it can't — otherwise it silently falls back to its training data, which defeats the point of RAG and produces answers that look grounded but aren't.
- **Stale index.** The vector store is a snapshot — if source documents change and the index isn't re-embedded, retrieval confidently returns outdated information. This needs an actual re-indexing pipeline/schedule, not a one-time embed-and-forget.
- **Context window overflow with many/large retrieved chunks.** Going back to [docs/01](01-genai-fundamentals.md): retrieved context + system prompt + conversation history + the question all share one token budget. A `k=10` retriever with large chunks can silently blow past the model's limit or crowd out conversation history — measure actual token counts, don't assume.

## Where load matters here specifically

Both the embedding call (per query) and the vector store lookup add latency on top of the LLM generation call — a RAG request is at minimum two network calls, often three (embed → retrieve → generate). See [docs/07-load-handling.md](07-load-handling.md) for why this compounds under concurrent load and what to do about it (caching embeddings for repeated/similar queries is the highest-leverage optimization here).
