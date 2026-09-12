"""
A minimal LangChain LCEL chain: prompt -> model -> output parser.

Uses langchain_core's FakeListChatModel by default so this runs with zero
API keys and zero cost — swap `build_model()` for a real one when you're
ready (see the commented-out line).

Run:
    python chain.py
Test:
    pytest test_chain.py
"""
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate


def build_model():
    # Swap this for a real model when you have an API key:
    #   from langchain_openai import ChatOpenAI
    #   return ChatOpenAI(model="gpt-4o-mini", temperature=0)
    return FakeListChatModel(responses=[
        "LangChain is a framework for composing LLM calls into pipelines.",
    ])


def build_chain():
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a terse technical assistant. Answer in one sentence."),
        ("human", "{question}"),
    ])
    model = build_model()
    parser = StrOutputParser()
    return prompt | model | parser  # this pipe syntax is LCEL


if __name__ == "__main__":
    chain = build_chain()
    print(chain.invoke({"question": "What is LangChain?"}))

    print("\nStreaming the same call:")
    for chunk in chain.stream({"question": "What is LangChain?"}):
        print(chunk, end="", flush=True)
    print()
