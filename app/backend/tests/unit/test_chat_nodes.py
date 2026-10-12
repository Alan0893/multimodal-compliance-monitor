"""Tests for chat message formatting sent to OpenAI-compatible endpoints."""

from __future__ import annotations

import asyncio

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from chat.nodes import make_context_answer_node, make_router_node


class _StructuredLLM:
    def __init__(self):
        self.messages = None

    async def ainvoke(self, messages):
        self.messages = messages
        return type("RouteDecision", (), {"route": "context"})()


class _LLM:
    def __init__(self):
        self.messages = None
        self.structured = _StructuredLLM()

    def with_structured_output(self, _schema):
        return self.structured

    async def ainvoke(self, messages):
        self.messages = messages
        return AIMessage(content="answer")


def _assert_single_system_message_at_start(messages):
    assert isinstance(messages[0], SystemMessage)
    assert sum(isinstance(message, SystemMessage) for message in messages) == 1
    assert isinstance(messages[-1], HumanMessage)


def test_router_combines_prompt_and_visual_context():
    llm = _LLM()
    router = make_router_node(llm)

    asyncio.run(
        router(
            {
                "context": "Detected: car: 5",
                "question": "How many cars are visible?",
                "classes_info": None,
            }
        )
    )

    messages = llm.structured.messages
    _assert_single_system_message_at_start(messages)
    assert "Current visual context:\nDetected: car: 5" in messages[0].content


def test_context_answer_combines_prompt_and_visual_context():
    llm = _LLM()
    context_answer = make_context_answer_node(llm)

    asyncio.run(
        context_answer(
            {
                "context": "Detected: car: 5",
                "question": "How many cars are visible?",
                "classes_info": None,
            }
        )
    )

    messages = llm.messages
    _assert_single_system_message_at_start(messages)
    assert "The user sees right now:\nDetected: car: 5" in messages[0].content
