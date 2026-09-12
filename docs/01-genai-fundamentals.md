# GenAI Fundamentals

## What an LLM actually does

A large language model takes a sequence of tokens and predicts the next one, repeatedly. Everything built on top — chat, agents, RAG — is scaffolding around that one operation. Keeping this in mind explains most of the "weird" behavior newcomers hit:

- **It has no memory between calls.** Every API call is stateless — "conversation history" is just the previous messages re-sent as part of the next prompt. This is *why* context windows and token costs matter: a long conversation means re-sending the whole thing, every turn.
- **It can't "look things up" unless you give it a way to.** Retrieval (RAG) and tool-calling exist specifically to get information into the prompt that the model wasn't trained on or can't reliably recall.
- **It's non-deterministic by default.** Same prompt, different output, unless you pin `temperature=0` (and even then, provider-side changes can shift results slightly over time). Design for this — don't assume identical inputs give identical outputs.

## Tokens, not words

Text is broken into tokens (roughly ¾ of a word in English, more for other languages/code). This matters practically:
- **Cost and context limits are token-based**, not character-based. A model with a 128k context window can fit ~100k words, not 128k words.
- **Truncation happens silently in bad implementations** — always know what happens when your prompt + retrieved context + history exceeds the model's limit (LangChain's message trimming utilities exist for exactly this).

## Embeddings — the other half of GenAI

An embedding model turns text into a vector (a list of numbers) such that semantically similar text ends up close together in that vector space. This is what makes semantic search / RAG possible: you embed a query, embed a document corpus once, and find the nearest vectors — no exact keyword match needed.

Two things people get wrong early:
- **Embeddings and chat models are usually different models** (e.g., `text-embedding-3-small` vs `gpt-4o-mini`) — you need both, and they're billed separately.
- **Chunking strategy matters more than model choice** for RAG quality — see [docs/05-rag-pipelines.md](05-rag-pipelines.md).

## Why "just call the API" stops working past a toy demo

A single `curl` call to an LLM API is a complete GenAI application for about a day of learning. Past that, you run into the actual engineering problems this repo is about:

| Problem | What handles it |
|---|---|
| Need to chain steps (retrieve → prompt → parse) reliably | LangChain (LCEL) |
| Need branching/looping based on the model's own decisions | LangGraph |
| Need the model to answer from your data, not just its training | RAG (docs/05) |
| Need a real UI, not a script | Full-stack architecture (docs/06) |
| Need it to survive more than one concurrent user | Load handling (docs/07) — the part almost no tutorial covers |
| Need to know when it's wrong | Observability & evals (docs/08) |

## Provider-agnostic note

This repo's examples default to OpenAI (`langchain-openai`) since it's the most common starting point, but LangChain and LangGraph are provider-agnostic — swapping `ChatOpenAI` for `ChatAnthropic`, `ChatBedrock`, or a local model via `ChatOllama` is usually a one-line change since they all implement the same `BaseChatModel` interface. Where an example matters for cost/latency reasons specifically, that's called out.
