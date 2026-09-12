import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_health_check(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"database": "ok", "redis": "ok"}


def test_ingest_then_chat_is_grounded_in_the_document(client):
    r = client.post("/ingest", params={
        "source": "support-hours.txt",
        "text": "Our support hours are 9am to 5pm Eastern, Monday through Friday.",
    })
    assert r.status_code == 200
    assert "document_id" in r.json()

    with client.stream("GET", "/chat", params={"question": "What are your support hours?", "session_id": "s1"}) as r:
        assert r.status_code == 200
        body = "".join(r.iter_text())

    assert body.rstrip().endswith("data: [DONE]")
    assert body.count("data: ") > 1  # genuinely streamed in multiple pieces


def test_chat_persists_conversation_history(client):
    with client.stream("GET", "/chat", params={"question": "hello", "session_id": "history-test"}) as r:
        for _ in r.iter_text():
            pass

    r = client.get("/history", params={"session_id": "history-test"})
    assert r.status_code == 200
    history = r.json()
    assert len(history) == 2
    assert history[0]["role"] == "human"
    assert history[0]["content"] == "hello"
    assert history[1]["role"] == "ai"


def test_history_is_isolated_per_session(client):
    with client.stream("GET", "/chat", params={"question": "q1", "session_id": "session-a"}) as r:
        for _ in r.iter_text():
            pass
    with client.stream("GET", "/chat", params={"question": "q2", "session_id": "session-b"}) as r:
        for _ in r.iter_text():
            pass

    history_a = client.get("/history", params={"session_id": "session-a"}).json()
    history_b = client.get("/history", params={"session_id": "session-b"}).json()

    assert history_a[0]["content"] == "q1"
    assert history_b[0]["content"] == "q2"


def test_rate_limit_rejects_excess_requests_from_one_session(client):
    statuses = []
    for i in range(35):  # default limit is 30/window — see app/config.py
        with client.stream("GET", "/chat", params={"question": f"q{i}", "session_id": "rate-limit-test"}) as r:
            statuses.append(r.status_code)
            if r.status_code == 200:
                for _ in r.iter_text():
                    pass

    assert 429 in statuses
    assert statuses.count(200) <= 30
