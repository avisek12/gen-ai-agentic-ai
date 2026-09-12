from graph import build_graph
from graph_with_memory import build_graph as build_memory_graph


def test_routes_to_tool_when_needed():
    app = build_graph()
    result = app.invoke({"question": "What's the weather like?"})
    assert result["needs_tool"] is True
    assert result["tool_result"] == "Sunny, 22C"
    assert "Based on the tool" in result["answer"]


def test_skips_tool_when_not_needed():
    app = build_graph()
    result = app.invoke({"question": "What is 2 + 2?"})
    assert result["needs_tool"] is False
    assert "tool_result" not in result
    assert "Direct answer" in result["answer"]


def test_checkpointer_persists_within_thread():
    app = build_memory_graph()
    cfg = {"configurable": {"thread_id": "t1"}}
    assert app.invoke({}, config=cfg)["count"] == 1
    assert app.invoke({}, config=cfg)["count"] == 2
    assert app.invoke({}, config=cfg)["count"] == 3


def test_checkpointer_isolates_threads():
    app = build_memory_graph()
    app.invoke({}, config={"configurable": {"thread_id": "isolated-a"}})
    result_b = app.invoke({}, config={"configurable": {"thread_id": "isolated-b"}})
    assert result_b["count"] == 1  # not affected by thread "a"
