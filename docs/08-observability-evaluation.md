# Observability & Evaluation

How you find out an LLM app is wrong before a user does — and, tying back to [docs/07](07-load-handling.md), how you know what to actually tune.

## Why this is harder than normal application observability

A normal API either returns the right answer or throws an error — you know which happened. An LLM call almost always "succeeds" (HTTP 200, well-formed text) while being **factually wrong, off-topic, or subtly unhelpful** — failure modes a status code can't catch. This is why LLM observability needs two additional layers beyond standard logging/metrics: **tracing** (what actually happened inside a multi-step chain/graph) and **evaluation** (was the output actually good).

## Tracing

For anything beyond a single prompt → single response, you need to see every intermediate step: what the retriever returned, what the model was actually prompted with (after templating), what a tool call's arguments and result were, and — for a LangGraph agent — which nodes ran and in what order. `langsmith` (LangChain's own tracing tool, installed automatically as a dependency of `langchain-core` in this repo — you'll notice it in the pytest plugin list when running this repo's test suites) integrates with both LangChain and LangGraph via environment variables (`LANGCHAIN_TRACING_V2=true`, `LANGCHAIN_API_KEY=...`) with no code changes to the chain/graph itself. Any equivalent tracing tool (OpenTelemetry-based alternatives exist too) needs to capture the same thing: the full prompt actually sent, not just the user's input, since templating/retrieval/history can change it substantially.

## Evaluation — knowing "good" from "bad" at scale

Manually reading outputs doesn't scale past a handful of test cases. Two practical approaches:

- **LLM-as-judge** — a second model call scores the first model's output against criteria (correctness, relevance, tone) or compares it to a reference answer. Cheaper to set up than human review, but inherits the judging model's own blind spots — validate the judge against a human-labeled sample before trusting it at scale.
- **Deterministic checks where possible** — if the output should contain a specific fact, a valid JSON structure, or pass a business rule, check that directly rather than asking another LLM to eyeball it. Faster, cheaper, and doesn't have the judge's own failure mode.

Build a small, real regression test set from actual production queries (including ones that previously failed) — this is worth more than a large synthetic set, because it tracks the failure modes you've actually seen, not hypothetical ones. Run it whenever you change a prompt, a model version, or a retrieval parameter — a prompt tweak that improves one case regressing three others is easy to miss without this.

## Guardrails

Checks applied to input and/or output, independent of the main model call:
- **Input guardrails** — reject or sanitize prompt-injection attempts, off-topic requests, or PII before it reaches the model (relevant directly to `aws-migration/terraform/customer-intake`'s design, where the system prompt itself is the first guardrail layer, backed by server-side validation of anything the model proposes — see that repo's README for the concrete pattern).
- **Output guardrails** — check the response doesn't leak system prompt content, doesn't claim to have done something it can't do (a common failure: an LLM claiming it "deployed" or "sent" something when it only generated text), and matches expected structure before it reaches the user.

The general principle, consistent with [docs/07](07-load-handling.md)'s "never trust free text parsing for something that writes files": **never let the model's own claim about what it did substitute for actually checking what happened.** If a tool call was supposed to run, verify it ran; if a structured output was expected, validate the structure server-side rather than trusting the model followed instructions.
