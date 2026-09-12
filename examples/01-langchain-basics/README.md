# 01 — LangChain Basics

Two runnable files:

- **`chain.py`** — the minimal LCEL pattern: `prompt | model | parser`. Run it, read it top to bottom — this three-part pipe is the building block for almost everything else in LangChain.
- **`memory_chain.py`** — a chat chain that remembers previous turns. Also documents two real API-churn facts found by actually running this against the currently installed LangChain version (not assumed from memory) — see the file's docstring.

## Run

```
pip install -r requirements.txt
python chain.py
python memory_chain.py
```

Both use a fake model (`FakeListChatModel`) so they run instantly with zero API cost. To try a real model, uncomment the `ChatOpenAI` line in `build_model()` / `memory_chain.py` and set `OPENAI_API_KEY`.

## Test

```
pytest test_chain.py -v
```

All four tests pass against the fake model — they check the actual chain/parser/history plumbing works, not the content of a real LLM's response (which is non-deterministic by design; see [docs/01](../../docs/01-genai-fundamentals.md)).
