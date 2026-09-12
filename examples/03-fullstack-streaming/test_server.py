from fastapi.testclient import TestClient

from server import app

client = TestClient(app)


def test_index_serves_html():
    r = client.get("/")
    assert r.status_code == 200
    assert b"Streaming Chat Demo" in r.content


def test_chat_streams_sse_chunks():
    with client.stream("GET", "/chat", params={"question": "hi"}) as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        body = "".join(r.iter_text())

    assert body.startswith("data: ")
    assert body.rstrip().endswith("data: [DONE]")
    # more than one SSE "data:" line means it actually streamed in pieces,
    # not just sent the whole response as one chunk
    assert body.count("data: ") > 1


def test_chat_requires_question_param():
    r = client.get("/chat")
    assert r.status_code == 422  # FastAPI's validation error for a missing required query param
