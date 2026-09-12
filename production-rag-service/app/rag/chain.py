"""
The generation half of RAG: retrieved context + question -> answer.
Retrieval itself happens separately (see retrieve.py) so the chain here
stays a plain LCEL pipeline — consistent with the parent repo's
docs/02-langchain-basics.md guidance to keep chains linear and let
LangGraph handle anything branchy.
"""
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from app.config import settings

SYSTEM_PROMPT = (
    "You are a helpful assistant. Answer the question using ONLY the "
    "provided context. If the context doesn't contain the answer, say "
    "you don't have enough information — do not use outside knowledge."
)


def build_model():
    if settings.openai_api_key:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=settings.chat_model, temperature=0)
    from langchain_core.language_models.fake_chat_models import FakeListChatModel
    return FakeListChatModel(responses=[
        "Based on the provided context, this is a fake grounded answer for local testing.",
    ])


def build_rag_chain():
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", "Context:\n{context}\n\nQuestion: {question}"),
    ])
    return prompt | build_model() | StrOutputParser()


def format_context(chunks) -> str:
    if not chunks:
        return "(no relevant context found)"
    return "\n\n".join(f"[{i+1}] {c.content}" for i, c in enumerate(chunks))
