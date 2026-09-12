"""
A chat chain that remembers previous turns using RunnableWithMessageHistory.

Two API-churn facts worth knowing, both confirmed by actually running this
against the installed package rather than assumed from memory:

1. The older `ConversationBufferMemory` / `ConversationChain` classes shown
   in a lot of tutorials no longer exist in current LangChain
   (`langchain.memory` is gone entirely) — RunnableWithMessageHistory is
   what replaced them.
2. RunnableWithMessageHistory itself now prints a deprecation warning
   ("Use LangGraph's built-in persistence instead") when you run this file.
   It still works today, but the actual current recommendation is
   LangGraph's checkpointer — see examples/02-langgraph-basics/ and
   docs/03-langgraph-basics.md. This file is kept as the LangChain-only
   version specifically to show what that migration looks like and why
   LangGraph persistence exists.

Run:
    python memory_chain.py
"""
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory


def build_chain_with_history():
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a terse assistant."),
        MessagesPlaceholder("history"),
        ("human", "{question}"),
    ])
    # Real model: ChatOpenAI(model="gpt-4o-mini") — fake here for a zero-cost demo.
    model = FakeListChatModel(responses=[
        "Nice to meet you.",
        "You told me your name a moment ago.",
    ])
    chain = prompt | model | StrOutputParser()

    # In-memory only — swap for a Redis/DynamoDB-backed history in a real
    # multi-instance deployment (see docs/07-load-handling.md).
    session_store: dict[str, InMemoryChatMessageHistory] = {}

    def get_history(session_id: str) -> InMemoryChatMessageHistory:
        if session_id not in session_store:
            session_store[session_id] = InMemoryChatMessageHistory()
        return session_store[session_id]

    return RunnableWithMessageHistory(
        chain, get_history, input_messages_key="question", history_messages_key="history",
    ), session_store


if __name__ == "__main__":
    chain, sessions = build_chain_with_history()
    cfg = {"configurable": {"session_id": "demo-user"}}

    print(chain.invoke({"question": "Hi, I'm Sam."}, config=cfg))
    print(chain.invoke({"question": "Do you remember my name?"}, config=cfg))
    print(f"\nMessages stored for this session: {len(sessions['demo-user'].messages)}")
