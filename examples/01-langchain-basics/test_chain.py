from chain import build_chain
from memory_chain import build_chain_with_history


def test_chain_invoke_returns_string():
    chain = build_chain()
    result = chain.invoke({"question": "What is LangChain?"})
    assert isinstance(result, str)
    assert len(result) > 0


def test_chain_stream_yields_chunks():
    chain = build_chain()
    chunks = list(chain.stream({"question": "test"}))
    assert len(chunks) > 0
    assert "".join(chunks)  # non-empty when joined


def test_memory_chain_accumulates_history():
    chain, sessions = build_chain_with_history()
    cfg = {"configurable": {"session_id": "test-session"}}

    chain.invoke({"question": "first turn"}, config=cfg)
    chain.invoke({"question": "second turn"}, config=cfg)

    # 2 human + 2 AI messages
    assert len(sessions["test-session"].messages) == 4


def test_memory_chain_isolates_sessions():
    chain, sessions = build_chain_with_history()
    chain.invoke({"question": "hi"}, config={"configurable": {"session_id": "user-a"}})
    chain.invoke({"question": "hi"}, config={"configurable": {"session_id": "user-b"}})

    assert "user-a" in sessions
    assert "user-b" in sessions
    assert sessions["user-a"] is not sessions["user-b"]
