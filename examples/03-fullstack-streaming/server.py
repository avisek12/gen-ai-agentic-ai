"""
A FastAPI backend that streams an LLM's response to the browser token by
token over Server-Sent Events (SSE), instead of waiting for the full
response and sending it all at once.

Why this matters: an LLM response can take several seconds to generate in
full. Streaming means the user sees the first words almost immediately —
the single biggest perceived-latency win available for a chat UI, and it
costs nothing extra since LCEL chains support streaming by default (see
docs/02-langchain-basics.md).

Run:
    uvicorn server:app --reload
Then open http://127.0.0.1:8000/ in a browser and try the chat box, or:
    curl -N "http://127.0.0.1:8000/chat?question=hello"
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

app = FastAPI(title="Fullstack Streaming Demo")

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def build_chain():
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful, concise assistant."),
        ("human", "{question}"),
    ])
    # Swap for a real model: from langchain_openai import ChatOpenAI; ChatOpenAI(model="gpt-4o-mini")
    model = FakeListChatModel(responses=[
        "This is a fake streamed response, arriving one token at a time, "
        "just like a real model's tokens would.",
    ])
    return prompt | model | StrOutputParser()


chain = build_chain()


@app.get("/")
async def index():
    return StreamingResponse(open(STATIC_DIR / "index.html", "rb"), media_type="text/html")


@app.get("/chat")
async def chat(question: str):
    """Server-Sent Events endpoint. Each `data: ...` line is one chunk;
    `data: [DONE]` signals the stream is finished."""

    async def event_stream():
        async for chunk in chain.astream({"question": question}):
            # SSE format requires each line to start with "data: " and the
            # event to end with a blank line.
            yield f"data: {chunk}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
