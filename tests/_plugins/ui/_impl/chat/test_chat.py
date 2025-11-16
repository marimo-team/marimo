# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest

from marimo._ai._types import (
    ChatMessage,
    ChatModelConfig,
    ChatModelConfigDict,
)
from marimo._plugins import ui
from marimo._plugins.ui._impl.chat.chat import (
    DEFAULT_CONFIG,
    DeleteChatMessageRequest,
    SendMessageRequest,
)
from marimo._runtime.functions import EmptyArgs
from marimo._runtime.requests import SetUIElementValueRequest
from marimo._runtime.runtime import Kernel
from tests.conftest import ExecReqProvider

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


def test_chat_init():
    def mock_model(
        messages: list[ChatMessage], config: ChatModelConfig
    ) -> str:
        del messages, config
        return "Mock response"

    chat = ui.chat(mock_model)
    assert chat._model == mock_model
    assert chat._chat_history == []
    assert chat.value == []
    assert chat._component_args["config"] == DEFAULT_CONFIG


def test_chat_with_prompts():
    def mock_model(
        messages: list[ChatMessage], config: ChatModelConfig
    ) -> str:
        del messages, config
        return "Mock response"

    prompts: list[str] = ["Hello", "How are you?"]
    chat = ui.chat(mock_model, prompts=prompts)
    assert chat._component_args["prompts"] == prompts


def test_chat_with_config():
    def mock_model(
        messages: list[ChatMessage], config: ChatModelConfig
    ) -> str:
        del messages, config
        return "Mock response"

    config: ChatModelConfigDict = {"temperature": 0.7, "max_tokens": 100}
    chat = ui.chat(mock_model, config=config)
    assert chat._component_args["config"] == {
        **DEFAULT_CONFIG,
        "temperature": 0.7,
        "max_tokens": 100,
    }


async def test_chat_send_prompt():
    def mock_model(
        messages: list[ChatMessage], config: ChatModelConfig
    ) -> str:
        del config
        return f"Response to: {messages[-1].content}"

    chat = ui.chat(mock_model)
    request = SendMessageRequest(
        messages=[ChatMessage(role="user", content="Hello")],
        config=ChatModelConfig(),
    )
    response: str = await chat._send_prompt(request)

    assert response == "Response to: Hello"
    assert len(chat._chat_history) == 2
    assert chat._chat_history[0].role == "user"
    assert chat._chat_history[0].content == "Hello"
    assert chat._chat_history[1].role == "assistant"
    assert chat._chat_history[1].content == "Response to: Hello"


async def test_chat_send_prompt_async_function():
    async def mock_model(
        messages: list[ChatMessage], config: ChatModelConfig
    ) -> str:
        del config
        await asyncio.sleep(0.01)
        return f"Response to: {messages[-1].content}"

    chat = ui.chat(mock_model)
    request = SendMessageRequest(
        messages=[ChatMessage(role="user", content="Hello")],
        config=ChatModelConfig(),
    )
    response: str = await chat._send_prompt(request)

    assert response == "Response to: Hello"
    assert len(chat._chat_history) == 2
    assert chat._chat_history[0].role == "user"
    assert chat._chat_history[0].content == "Hello"
    assert chat._chat_history[1].role == "assistant"
    assert chat._chat_history[1].content == "Response to: Hello"


async def test_chat_send_prompt_async_generator():
    async def mock_model(
        messages: list[ChatMessage], config: ChatModelConfig
    ) -> AsyncIterator[str]:
        del config
        del messages
        for i in range(3):
            await asyncio.sleep(0.01)
            yield str(i)

    chat = ui.chat(mock_model)
    request = SendMessageRequest(
        messages=[ChatMessage(role="user", content="Hello")],
        config=ChatModelConfig(),
    )
    response: str = await chat._send_prompt(request)

    # the last yielded value is the response
    assert response == "2"
    assert len(chat._chat_history) == 2
    assert chat._chat_history[0].role == "user"
    assert chat._chat_history[0].content == "Hello"
    assert chat._chat_history[1].role == "assistant"
    assert chat._chat_history[1].content == "2"


async def test_chat_streaming_sends_messages():
    """Test that streaming async generators send messages via _send_message"""
    sent_messages = []

    async def mock_streaming_model(
        messages: list[ChatMessage], config: ChatModelConfig
    ) -> AsyncIterator[str]:
        del config, messages
        # Simulate streaming response
        accumulated = ""
        for word in ["Hello", "world", "!"]:
            accumulated += word + " "
            yield accumulated.strip()

    chat = ui.chat(mock_streaming_model)

    # Mock _send_message to capture calls
    original_send_message = chat._send_message

    def capture_send_message(message: dict[str, object], buffers):  # noqa: ARG001
        sent_messages.append(message)
        # Don't actually send to avoid needing kernel context

    chat._send_message = capture_send_message

    request = SendMessageRequest(
        messages=[ChatMessage(role="user", content="Test")],
        config=ChatModelConfig(),
    )

    response: str = await chat._send_prompt(request)

    # Verify final response
    assert response == "Hello world !"

    # Verify streaming messages were sent
    # Should have sent chunks for each yield, plus final message
    assert len(sent_messages) >= 3

    # Check that messages have streaming structure
    for msg in sent_messages[:-1]:  # All but last
        assert msg["type"] == "stream_chunk"
        assert "message_id" in msg
        assert "content" in msg
        assert not msg["is_final"]

    # Last message should be final
    assert sent_messages[-1]["type"] == "stream_chunk"
    assert sent_messages[-1]["is_final"]
    assert sent_messages[-1]["content"] == "Hello world !"


def test_chat_get_history():
    def mock_model(
        messages: list[ChatMessage], config: ChatModelConfig
    ) -> str:
        del messages, config
        return "Mock response"

    chat = ui.chat(mock_model)
    history = chat._get_chat_history(EmptyArgs())
    assert history.messages == []

    chat._chat_history = [
        ChatMessage(role="user", content="Hello"),
        ChatMessage(role="assistant", content="Hi there!"),
    ]

    history = chat._get_chat_history(EmptyArgs())
    assert len(history.messages) == 2
    assert history.messages[0].role == "user"
    assert history.messages[0].content == "Hello"
    assert history.messages[1].role == "assistant"
    assert history.messages[1].content == "Hi there!"


def test_chat_delete_history():
    def mock_model(
        messages: list[ChatMessage], config: ChatModelConfig
    ) -> str:
        del messages, config
        return "Mock response"

    chat = ui.chat(mock_model)
    chat._delete_chat_history(EmptyArgs())
    assert chat._chat_history == []
    assert chat.value == []

    chat._chat_history = [
        ChatMessage(role="user", content="Hello"),
        ChatMessage(role="assistant", content="Hi there!"),
    ]

    chat._delete_chat_history(EmptyArgs())
    assert chat._chat_history == []
    assert chat.value == []


def test_chat_delete_message():
    def mock_model(
        messages: list[ChatMessage], config: ChatModelConfig
    ) -> str:
        del messages, config
        return "Mock response"

    chat = ui.chat(mock_model)

    with pytest.raises(ValueError, match="Invalid message index"):
        chat._delete_chat_message(DeleteChatMessageRequest(index=0))

    chat._chat_history = [
        ChatMessage(role="user", content="Hello"),
        ChatMessage(role="assistant", content="Hi there!"),
    ]

    chat._delete_chat_message(DeleteChatMessageRequest(index=0))
    assert len(chat._chat_history) == 1
    assert chat._chat_history[0].role == "assistant"
    assert chat._chat_history[0].content == "Hi there!"


def test_chat_convert_value():
    def mock_model(
        messages: list[ChatMessage], config: ChatModelConfig
    ) -> str:
        del messages, config
        return "Mock response"

    chat = ui.chat(mock_model)
    value: dict[str, list[dict[str, str]]] = {
        "messages": [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
    }

    converted: list[ChatMessage] = chat._convert_value(value)
    assert len(converted) == 2
    assert converted[0].role == "user"
    assert converted[0].content == "Hello"
    assert converted[1].role == "assistant"
    assert converted[1].content == "Hi there!"


def test_chat_convert_value_invalid():
    def mock_model(
        messages: list[ChatMessage], config: ChatModelConfig
    ) -> str:
        del messages, config
        return "Mock response"

    chat = ui.chat(mock_model)

    with pytest.raises(ValueError, match="Invalid chat history format"):
        chat._convert_value({"invalid": "format"})


async def test_chat_with_on_message():
    def mock_model(
        messages: list[ChatMessage], config: ChatModelConfig
    ) -> str:
        del messages, config
        return "Mock response"

    on_message_called = False

    def on_message(messages: list[ChatMessage]) -> None:
        del messages
        nonlocal on_message_called
        on_message_called = True

    chat = ui.chat(mock_model, on_message=on_message)
    request = SendMessageRequest(
        messages=[ChatMessage(role="user", content="Hello")],
        config=ChatModelConfig(),
    )
    await chat._send_prompt(request)

    assert on_message_called


def test_chat_with_show_configuration_controls():
    def mock_model(
        messages: list[ChatMessage], config: ChatModelConfig
    ) -> str:
        del messages, config
        return "Mock response"

    chat = ui.chat(mock_model, show_configuration_controls=True)
    assert chat._component_args["show-configuration-controls"] is True


async def test_chat_clear_messages():
    def mock_model(
        messages: list[ChatMessage], config: ChatModelConfig
    ) -> str:
        del messages, config
        return "Mock response"

    chat = ui.chat(mock_model)
    chat._chat_history = [
        ChatMessage(role="user", content="Hello"),
        ChatMessage(role="assistant", content="Hi there!"),
    ]

    assert chat._convert_value({"messages": []}) == []


async def test_chat_send_message_enqueues_ui_element_request(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    # assert that the RPC which updates the chatbot history triggers
    # a SetUIElementValueRequest

    control_requests = []
    # the RPC uses enqueue_control_request() to trigger the UI Element update
    k.enqueue_control_request = lambda r: control_requests.append(r)
    await k.run(
        [
            exec_req.get(
                """
                import marimo as mo
                def f(messages, config):
                    return "response"

                chatbot = mo.ui.chat(f)
                """
            ),
        ]
    )

    assert not control_requests
    chatbot = k.globals["chatbot"]
    request = SendMessageRequest(
        messages=[ChatMessage(role="user", content="Hello")],
        config=ChatModelConfig(),
    )
    await chatbot._send_prompt(request)
    assert len(control_requests) == 1
    assert isinstance(control_requests[0], SetUIElementValueRequest)
