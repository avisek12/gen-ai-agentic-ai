# LangChain Basics

Runnable, tested code for everything here: [`examples/01-langchain-basics/`](../examples/01-langchain-basics/).

## LCEL — the pipe operator is the whole idea

```python
chain = prompt | model | parser
```

This is LangChain Expression Language (LCEL). Each piece is a `Runnable` — something with `.invoke()`, `.stream()`, `.batch()`, and their async equivalents (`.ainvoke()`, `.astream()`, `.abatch()`) already implemented consistently. The `|` composes them into a pipeline where each stage's output becomes the next stage's input.

Why this matters more than it looks: **you get streaming and async for free** once every piece in the chain supports it — you didn't write any streaming logic, `chain.stream(...)` just works because `prompt`, `model`, and `parser` each know how to stream. This is directly relevant to [docs/06](06-fullstack-architecture.md) and [docs/07](07-load-handling.md) — the async methods are what make a full-stack backend handle concurrent requests without blocking.

## Prompts

`ChatPromptTemplate.from_messages([...])` builds a templated prompt from a list of `(role, template)` tuples. `{variable}` placeholders get filled in at `.invoke()` time:

```python
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a terse assistant."),
    ("human", "{question}"),
])
```

## Output parsers

The model returns a message object, not a plain string. `StrOutputParser()` extracts just the text content. For structured output (JSON matching a schema), use `.with_structured_output(YourPydanticModel)` on the model instead of a separate parser — it uses the model's native structured-output/tool-calling support rather than parsing free text, which is far more reliable.

## Memory — and a real API-churn warning

A lot of tutorials still teach `ConversationBufferMemory` / `ConversationChain`. **These no longer exist** in current LangChain (`langchain.memory` is gone entirely) — this was confirmed by actually trying to import it, not assumed. The current pattern is `RunnableWithMessageHistory`, wrapping a chain with a function that returns a `ChatMessageHistory` per session id:

```python
chain_with_history = RunnableWithMessageHistory(
    chain, get_history, input_messages_key="question", history_messages_key="history",
)
```

**But this itself now prints a deprecation warning** — `RunnableWithMessageHistory is deprecated. Use LangGraph's built-in persistence instead.` The actual current recommendation is LangGraph's checkpointer (see [docs/03](03-langgraph-basics.md)), even for a flow that's otherwise pure LangChain. This is a good example of why this repo tests everything against the real installed package instead of writing from memory — LangChain's API moves fast enough that "what the tutorial says" and "what currently works without a warning" regularly diverge.

## Tools

```python
from langchain_core.tools import tool

@tool
def get_weather(city: str) -> str:
    """Get the current weather for a city."""
    return "Sunny, 22C"

model_with_tools = model.bind_tools([get_weather])
```

`bind_tools` doesn't call the function for you — it tells the model the tool exists and lets the model's response include a request to call it (`response.tool_calls`). Your code is still responsible for actually calling `get_weather` and feeding the result back in. This "the model decides, your code executes" loop is exactly what LangGraph exists to structure once it needs to repeat — see [docs/04-agentic-patterns.md](04-agentic-patterns.md).

## When plain LangChain (no graph) is the right call

If your flow is genuinely linear — one retrieval, one prompt, one generation, done — a chain is simpler than a graph and you should use it. Reach for LangGraph specifically when the *next step* depends on a decision made during execution, not before it. See the decision guide in [docs/03-langgraph-basics.md](03-langgraph-basics.md).
