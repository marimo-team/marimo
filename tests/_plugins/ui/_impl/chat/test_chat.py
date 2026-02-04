# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest

from marimo._ai._types import (
    ChatMessage,
    ChatModelConfig,
    ChatModelConfigDict,
)
from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins import ui
from marimo._plugins.ui._impl.chat.chat import (
    DEFAULT_CONFIG,
    ChunkSerializer,
    DeleteChatMessageRequest,
    SendMessageRequest,
)
from marimo._runtime.commands import UpdateUIElementCommand
from marimo._runtime.functions import EmptyArgs
from marimo._runtime.runtime import Kernel
from tests.conftest import ExecReqProvider

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


def assert_single_message(
    sent_messages: list[dict],
    expected_delta: str,
    *,
    use_contains: bool = False,
) -> None:
    """Helper to assert the standard 4-message pattern for non-streaming responses.

    Args:
        sent_messages: List of messages sent via _send_message
        expected_delta: The expected text in the text-delta message
        use_contains: If True, check if expected_delta is contained in the delta,
                      otherwise check for exact equality
    """
    # Verify proper messages were sent: text-start, text-delta, text-end, final
    assert len(sent_messages) == 4

    # Message 0: text-start
    assert sent_messages[0]["type"] == "stream_chunk"
    assert sent_messages[0]["content"]["type"] == "text-start"
    assert sent_messages[0]["is_final"] is False

    # Message 1: text-delta
    assert sent_messages[1]["type"] == "stream_chunk"
    assert sent_messages[1]["content"]["type"] == "text-delta"
    if use_contains:
        assert expected_delta in sent_messages[1]["content"]["delta"]
    else:
        assert sent_messages[1]["content"]["delta"] == expected_delta
    assert sent_messages[1]["is_final"] is False

    # Message 2: text-end
    assert sent_messages[2]["type"] == "stream_chunk"
    assert sent_messages[2]["content"]["type"] == "text-end"
    assert sent_messages[2]["is_final"] is False

    # Message 3: final
    assert sent_messages[3]["type"] == "stream_chunk"
    assert sent_messages[3]["content"] is None
    assert sent_messages[3]["is_final"] is True


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
        # Messages come in with parts from the frontend, but for testing
        # we can send them with content
        if messages[-1].content:
            content = messages[-1].content
        else:
            content = messages[-1].parts[0].text  # type: ignore
        return f"Response to: {content}"

    chat = ui.chat(mock_model)

    sent_messages: list[dict] = []

    def capture_send_message(message: dict, buffers):  # noqa: ARG001
        sent_messages.append(message)

    chat._send_message = capture_send_message

    request = SendMessageRequest(
        messages=[ChatMessage(role="user", content="Hello")],
        config=ChatModelConfig(),
    )
    response = await chat._send_prompt(request)

    # Non-streaming now also returns None
    assert response is None

    # Verify proper messages were sent
    assert_single_message(sent_messages, "Response to: Hello")

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

    sent_messages: list[dict] = []

    def capture_send_message(message: dict, buffers):  # noqa: ARG001
        sent_messages.append(message)

    chat._send_message = capture_send_message

    request = SendMessageRequest(
        messages=[ChatMessage(role="user", content="Hello")],
        config=ChatModelConfig(),
    )
    response = await chat._send_prompt(request)

    # Non-streaming now also returns None
    assert response is None

    # Verify proper messages were sent
    assert_single_message(sent_messages, "Response to: Hello")

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
        # Yield delta chunks (new content only)
        for i in range(3):
            await asyncio.sleep(0.01)
            yield str(i)

    chat = ui.chat(mock_model)

    sent_messages: list[dict] = []

    def capture_send_message(message: dict, buffers):  # noqa: ARG001
        sent_messages.append(message)

    chat._send_message = capture_send_message

    request = SendMessageRequest(
        messages=[ChatMessage(role="user", content="Hello")],
        config=ChatModelConfig(),
    )
    response = await chat._send_prompt(request)

    # Streaming returns None
    assert response is None
    # Check that chunks were sent
    assert len(sent_messages) > 0
    # Check final message is marked as final
    assert sent_messages[-1]["is_final"] is True

    # String generators now update chat history with accumulated text
    assert len(chat._chat_history) == 2
    assert chat._chat_history[0].role == "user"
    assert chat._chat_history[1].role == "assistant"
    assert chat._chat_history[1].content == "012"


async def test_chat_streaming_sends_messages():
    """Test that streaming async generators send messages via _send_message"""
    sent_messages = []

    async def mock_streaming_model(
        messages: list[ChatMessage], config: ChatModelConfig
    ) -> AsyncIterator[str]:
        del config, messages
        # Simulate streaming response with delta chunks (new content only)
        for word in ["Hello", " ", "world", " ", "!"]:
            yield word

    chat = ui.chat(mock_streaming_model)

    def capture_send_message(message: dict[str, object], buffers):  # noqa: ARG001
        sent_messages.append(message)
        # Don't actually send to avoid needing kernel context

    chat._send_message = capture_send_message

    request = SendMessageRequest(
        messages=[ChatMessage(role="user", content="Test")],
        config=ChatModelConfig(),
    )

    response = await chat._send_prompt(request)

    # Streaming returns None
    assert response is None

    # Verify streaming messages were sent
    # Should have text-start, text-deltas, text-end, plus final None message
    assert len(sent_messages) >= 7  # start + 5 deltas + end + final

    # Check that messages have streaming structure
    for msg in sent_messages[:-1]:  # All but last
        assert msg["type"] == "stream_chunk"
        assert "message_id" in msg
        assert "content" in msg
        assert not msg["is_final"]

    # Last message should be final with None content
    assert sent_messages[-1]["type"] == "stream_chunk"
    assert sent_messages[-1]["is_final"]
    assert sent_messages[-1]["content"] is None

    # String generators now update chat history with accumulated text
    assert len(chat._chat_history) == 2
    assert chat._chat_history[0].role == "user"
    assert chat._chat_history[1].role == "assistant"
    assert chat._chat_history[1].content == "Hello world !"


async def test_chat_sync_generator_streaming():
    """Test that sync generators also work for streaming"""
    sent_messages = []

    def mock_streaming_model(
        messages: list[ChatMessage], config: ChatModelConfig
    ):
        del config, messages
        # Simulate streaming response with delta chunks (new content only)
        yield from ["Hello", " ", "world", " ", "!"]

    chat = ui.chat(mock_streaming_model)

    def capture_send_message(message: dict[str, object], buffers):  # noqa: ARG001
        sent_messages.append(message)

    chat._send_message = capture_send_message

    request = SendMessageRequest(
        messages=[ChatMessage(role="user", content="Test")],
        config=ChatModelConfig(),
    )

    response = await chat._send_prompt(request)

    # Streaming returns None
    assert response is None

    # Verify streaming messages were sent
    # Should have text-start, text-deltas, text-end, plus final None message
    assert len(sent_messages) >= 7

    # Check that messages have streaming structure
    for msg in sent_messages[:-1]:  # All but last
        assert msg["type"] == "stream_chunk"
        assert "message_id" in msg
        assert "content" in msg
        assert not msg["is_final"]

    # Last message should be final with None content
    assert sent_messages[-1]["type"] == "stream_chunk"
    assert sent_messages[-1]["is_final"]
    assert sent_messages[-1]["content"] is None

    # String generators now update chat history with accumulated text
    assert len(chat._chat_history) == 2
    assert chat._chat_history[0].role == "user"
    assert chat._chat_history[1].role == "assistant"
    assert chat._chat_history[1].content == "Hello world !"


async def test_chat_streaming_complete_response():
    """Test that streaming sends all chunks correctly"""
    sent_messages = []

    def mock_streaming_model_with_empty_final(
        messages: list[ChatMessage], config: ChatModelConfig
    ):
        del config, messages
        # Simulate delta-based streaming
        yield "Hello "
        yield "world"
        yield "!"
        # No more content - generator ends

    chat = ui.chat(mock_streaming_model_with_empty_final)

    def capture_send_message(message: dict, buffers):  # noqa: ARG001
        sent_messages.append(message)

    chat._send_message = capture_send_message

    request = SendMessageRequest(
        messages=[ChatMessage(role="user", content="Test")],
        config=ChatModelConfig(),
    )

    response = await chat._send_prompt(request)

    # Streaming returns None
    assert response is None
    # Verify all chunks were sent
    assert len(sent_messages) >= 4  # text-start + 3 deltas + text-end + final
    assert sent_messages[-1]["is_final"]

    # String generators now update chat history with accumulated text
    assert len(chat._chat_history) == 2
    assert chat._chat_history[0].role == "user"
    assert chat._chat_history[1].role == "assistant"
    assert chat._chat_history[1].content == "Hello world!"


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
    """Test _convert_value with messages in parts format."""

    def mock_model(
        messages: list[ChatMessage], config: ChatModelConfig
    ) -> str:
        del messages, config
        return "Mock response"

    chat = ui.chat(mock_model)
    value = {
        "messages": [
            {
                "role": "user",
                "parts": [{"type": "text", "text": "Hello"}],
            },
            {
                "role": "assistant",
                "parts": [{"type": "text", "text": "Hi there!"}],
            },
        ]
    }

    converted: list[ChatMessage] = chat._convert_value(value)
    assert len(converted) == 2
    assert converted[0].role == "user"
    assert len(converted[0].parts) == 1
    assert converted[1].role == "assistant"
    assert len(converted[1].parts) == 1


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
    async def mock_model(
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
    # a UpdateUIElementRequest

    control_requests = []
    # the RPC uses enqueue_control_request() to trigger the UI Element update
    k.enqueue_control_request = lambda r: control_requests.append(r)
    await k.run(
        [
            exec_req.get(
                """
                import marimo as mo
                async def f(messages, config):
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
    assert isinstance(control_requests[0], UpdateUIElementCommand)


def test_send_chat_message_helper():
    """Test the _send_chat_message helper method."""

    def mock_model(
        messages: list[ChatMessage], config: ChatModelConfig
    ) -> str:
        del messages, config
        return "Mock response"

    chat = ui.chat(mock_model)

    sent_messages: list[dict] = []

    def capture_send_message(message: dict, buffers):  # noqa: ARG001
        sent_messages.append(message)

    chat._send_message = capture_send_message

    # Send a non-final message
    chat._send_chat_message(
        message_id="msg-123", content="Hello", is_final=False
    )

    assert sent_messages == [
        {
            "type": "stream_chunk",
            "message_id": "msg-123",
            "content": "Hello",
            "is_final": False,
        }
    ]

    # Send a final message
    chat._send_chat_message(
        message_id="msg-123", content="Hello world", is_final=True
    )
    assert sent_messages == [
        {
            "type": "stream_chunk",
            "message_id": "msg-123",
            "content": "Hello",
            "is_final": False,
        },
        {
            "type": "stream_chunk",
            "message_id": "msg-123",
            "content": "Hello world",
            "is_final": True,
        },
    ]


def test_send_chat_message_with_dict_content():
    """Test _send_chat_message with dict content (pydantic-ai mode)."""

    def mock_model(
        messages: list[ChatMessage], config: ChatModelConfig
    ) -> str:
        del messages, config
        return "Mock response"

    chat = ui.chat(mock_model)

    sent_messages: list[dict] = []

    def capture_send_message(message: dict, buffers):  # noqa: ARG001
        sent_messages.append(message)

    chat._send_message = capture_send_message

    # Send dict content (like pydantic-ai serialized chunks)
    chunk_content = {"type": "text-delta", "textDelta": "Hello"}
    chat._send_chat_message(
        message_id="msg-456", content=chunk_content, is_final=False
    )

    assert len(sent_messages) == 1
    assert sent_messages[0]["content"] == chunk_content


def test_send_chat_message_with_none_content():
    """Test _send_chat_message with None content (final message for pydantic-ai)."""

    def mock_model(
        messages: list[ChatMessage], config: ChatModelConfig
    ) -> str:
        del messages, config
        return "Mock response"

    chat = ui.chat(mock_model)

    sent_messages: list[dict] = []

    def capture_send_message(message: dict, buffers):  # noqa: ARG001
        sent_messages.append(message)

    chat._send_message = capture_send_message

    # Send None content (final message indicator for pydantic-ai)
    chat._send_chat_message(message_id="msg-789", content=None, is_final=True)
    assert sent_messages == [
        {
            "type": "stream_chunk",
            "message_id": "msg-789",
            "content": None,
            "is_final": True,
        }
    ]


def test_convert_value_with_list_input():
    """Test _convert_value raises on invalid list input."""
    from typing import Any, cast

    def mock_model(
        messages: list[ChatMessage], config: ChatModelConfig
    ) -> str:
        del messages, config
        return "Mock response"

    chat = ui.chat(mock_model)

    # Test that passing a list directly raises ValueError
    with pytest.raises(ValueError, match="Invalid chat history format"):
        chat._convert_value(cast(Any, [{"role": "user", "content": "Hello"}]))


@pytest.mark.parametrize("use_async", [True, False])
async def test_vercel_messages_streaming(use_async: bool):
    """Test custom model (sync/async) streaming with dict chunks."""
    sent_messages: list[dict] = []

    chunks = [
        {"type": "text-start", "id": "text-1"},
        {"type": "text-delta", "id": "text-1", "delta": "Hello"},
        {"type": "text-delta", "id": "text-1", "delta": " world"},
        {"type": "text-end", "id": "text-1"},
    ]

    async def async_model(
        messages: list[ChatMessage], config: ChatModelConfig
    ):
        del messages, config
        for chunk in chunks:
            yield chunk

    def sync_model(messages: list[ChatMessage], config: ChatModelConfig):
        del messages, config
        yield from chunks

    custom_model = async_model if use_async else sync_model
    chat = ui.chat(custom_model)

    def capture_send_message(message: dict, buffers):  # noqa: ARG001
        sent_messages.append(message)

    chat._send_message = capture_send_message

    request = SendMessageRequest(
        messages=[ChatMessage(role="user", content="Hello")],
        config=ChatModelConfig(),
    )
    response = await chat._send_prompt(request)

    assert response is None

    # Extract message_id from first message for comparison
    message_id = sent_messages[0]["message_id"]

    assert sent_messages == [
        {
            "type": "stream_chunk",
            "message_id": message_id,
            "content": chunks[0],
            "is_final": False,
        },
        {
            "type": "stream_chunk",
            "message_id": message_id,
            "content": chunks[1],
            "is_final": False,
        },
        {
            "type": "stream_chunk",
            "message_id": message_id,
            "content": chunks[2],
            "is_final": False,
        },
        {
            "type": "stream_chunk",
            "message_id": message_id,
            "content": chunks[3],
            "is_final": False,
        },
        {
            "type": "stream_chunk",
            "message_id": message_id,
            "content": None,
            "is_final": True,
        },
    ]


def test_serialize_vercel_ai_chunk_dict():
    """Test ChunkSerializer with dict input."""
    sent_chunks: list[dict] = []

    def on_send_chunk(chunk: dict):
        sent_chunks.append(chunk)

    serializer = ChunkSerializer(on_send_chunk=on_send_chunk)

    # Dict input should pass through unchanged
    chunk = {"type": "text-delta", "id": "text-1", "delta": "Hello"}
    serializer.handle_chunk(chunk)
    assert sent_chunks == [chunk]


def test_serialize_plain_string():
    """Test ChunkSerializer with plain string input."""
    sent_chunks: list[dict] = []

    def on_send_chunk(chunk: dict):
        sent_chunks.append(chunk)

    serializer = ChunkSerializer(on_send_chunk=on_send_chunk)

    # Plain strings should be wrapped in text-start/text-delta chunks
    serializer.handle_chunk("Hello")
    serializer.handle_chunk(" world")
    serializer.on_end()

    # Should have text-start, two text-deltas, and text-end
    assert len(sent_chunks) == 4
    assert sent_chunks[0]["type"] == "text-start"
    text_id = sent_chunks[0]["id"]
    assert sent_chunks[1] == {
        "type": "text-delta",
        "id": text_id,
        "delta": "Hello",
    }
    assert sent_chunks[2] == {
        "type": "text-delta",
        "id": text_id,
        "delta": " world",
    }
    assert sent_chunks[3] == {"type": "text-end", "id": text_id}


def test_serialize_mixed_chunks():
    """Test ChunkSerializer with mixed dict and string chunks."""
    sent_chunks: list[dict] = []

    def on_send_chunk(chunk: dict):
        sent_chunks.append(chunk)

    serializer = ChunkSerializer(on_send_chunk=on_send_chunk)

    # Send a dict chunk, then strings, then another dict
    serializer.handle_chunk({"type": "reasoning-start", "id": "r-1"})
    serializer.handle_chunk("text1")
    serializer.handle_chunk("text2")
    serializer.handle_chunk({"type": "reasoning-end", "id": "r-1"})
    serializer.on_end()

    # Dict chunks are sent as-is, strings are wrapped in text-start/delta/end
    # text-end is only sent when on_end() is called
    assert len(sent_chunks) == 6
    assert sent_chunks[0] == {"type": "reasoning-start", "id": "r-1"}
    assert sent_chunks[1]["type"] == "text-start"
    text_id = sent_chunks[1]["id"]
    assert sent_chunks[2] == {
        "type": "text-delta",
        "id": text_id,
        "delta": "text1",
    }
    assert sent_chunks[3] == {
        "type": "text-delta",
        "id": text_id,
        "delta": "text2",
    }
    # Dict chunk is sent as-is, even after strings
    assert sent_chunks[4] == {"type": "reasoning-end", "id": "r-1"}
    # text-end is sent when on_end() is called
    assert sent_chunks[5] == {"type": "text-end", "id": text_id}


def test_serialize_only_dict_chunks():
    """Test ChunkSerializer with only dict chunks (no text)."""
    sent_chunks: list[dict] = []

    def on_send_chunk(chunk: dict):
        sent_chunks.append(chunk)

    serializer = ChunkSerializer(on_send_chunk=on_send_chunk)

    # Send only dict chunks
    serializer.handle_chunk({"type": "reasoning-start", "id": "r-1"})
    serializer.handle_chunk({"type": "reasoning-end", "id": "r-1"})
    serializer.on_end()

    # Should have only the dict chunks, no text-end added
    assert sent_chunks == [
        {"type": "reasoning-start", "id": "r-1"},
        {"type": "reasoning-end", "id": "r-1"},
    ]


def test_serialize_str_subclass():
    """Ensure str subclasses (like weave's BoxedStr) are coerced to plain str."""

    class BoxedStr(str):
        """Mock of weave's BoxedStr - a str subclass with extra attributes."""

        def __new__(cls, value):
            instance = super().__new__(cls, value)
            instance._id = "trace_123"
            instance.ref = "weave://entity/project/..."
            return instance

    sent_chunks: list[dict] = []

    def on_send_chunk(chunk: dict):
        sent_chunks.append(chunk)

    serializer = ChunkSerializer(on_send_chunk=on_send_chunk)

    boxed = BoxedStr("Hello from weave")
    serializer.handle_chunk(boxed)

    # Should have text-start and text-delta
    assert len(sent_chunks) == 2
    assert sent_chunks[0]["type"] == "text-start"
    assert sent_chunks[1]["type"] == "text-delta"
    # Critical: delta should be plain str, not BoxedStr
    assert sent_chunks[1]["delta"] == "Hello from weave"
    assert type(sent_chunks[1]["delta"]) is str  # Exact type check


@pytest.mark.skipif(
    not DependencyManager.weave.has(),
    reason="weave is not installed",
)
def test_serialize_weave_boxed_str():
    """Integration test with actual weave BoxedStr."""
    import weave

    @weave.op
    def traced_fn() -> str:
        return "traced response"

    result = traced_fn()

    sent_chunks: list[dict] = []

    def on_send_chunk(chunk: dict):
        sent_chunks.append(chunk)

    serializer = ChunkSerializer(on_send_chunk=on_send_chunk)
    serializer.handle_chunk(result)

    assert len(sent_chunks) == 2
    assert sent_chunks[1]["type"] == "text-delta"
    assert type(sent_chunks[1]["delta"]) is str


@pytest.mark.skipif(
    not DependencyManager.pydantic_ai.has(),
    reason="Pydantic AI is not installed",
)
def test_serialize_pydantic_chunk():
    """Test ChunkSerializer with pydantic BaseChunk input."""
    from pydantic_ai.ui.vercel_ai.response_types import TextDeltaChunk

    sent_chunks: list[dict] = []

    def on_send_chunk(chunk: dict):
        sent_chunks.append(chunk)

    serializer = ChunkSerializer(on_send_chunk=on_send_chunk)

    chunk = TextDeltaChunk(id="text-1", delta="Hello")
    serializer.handle_chunk(chunk)

    # Should be a dict with camelCase keys (by_alias=True)
    assert sent_chunks == [
        {"type": "text-delta", "id": "text-1", "delta": "Hello"}
    ]


@pytest.mark.skipif(
    not DependencyManager.pydantic_ai.has(),
    reason="Pydantic AI is not installed",
)
def test_serialize_pydantic_v5():
    """Test ChunkSerializer excludes providerMetadata from tool-input-start for SDK v5.

    The Vercel AI SDK v5 schema drifts from v6, so we need to use Pydantic's handling.

    Since pydantic-ai uses toolCallId, providerMetadata must be excluded.
    See: https://github.com/pydantic/pydantic-ai/pull/4166
    """
    from pydantic_ai.ui.vercel_ai.response_types import ToolInputStartChunk

    sent_chunks: list[dict] = []

    def on_send_chunk(chunk: dict):
        sent_chunks.append(chunk)

    serializer = ChunkSerializer(on_send_chunk=on_send_chunk)

    # Create chunk with providerMetadata (like Google Gemini produces)
    chunk = ToolInputStartChunk(
        tool_call_id="tc_1",
        tool_name="my_tool",
        provider_metadata={
            "pydantic_ai": {
                "id": "test_id",
                "provider_name": "google-gla",
                "provider_details": {"thought_signature": "encrypted_data"},
            }
        },
    )
    serializer.handle_chunk(chunk)

    # providerMetadata should be excluded for SDK v5 compatibility
    assert sent_chunks == [
        {
            "type": "tool-input-start",
            "toolCallId": "tc_1",
            "toolName": "my_tool",
        }
    ]


@pytest.mark.skipif(
    not DependencyManager.pydantic_ai.has(),
    reason="Pydantic AI is not installed",
)
@pytest.mark.parametrize("use_async", [True, False])
async def test_vercel_messages_with_pydantic_chunks(use_async: bool):
    """Test custom model (sync/async) with pydantic-ai response_types chunks."""
    from pydantic_ai.ui.vercel_ai.response_types import (
        TextDeltaChunk,
        TextEndChunk,
        TextStartChunk,
    )

    sent_messages: list[dict] = []

    chunks = [
        TextStartChunk(id="text-1"),
        TextDeltaChunk(id="text-1", delta="Hello"),
        TextEndChunk(id="text-1"),
    ]

    async def async_model(
        messages: list[ChatMessage], config: ChatModelConfig
    ):
        del messages, config
        for chunk in chunks:
            yield chunk

    def sync_model(messages: list[ChatMessage], config: ChatModelConfig):
        del messages, config
        yield from chunks

    custom_model = async_model if use_async else sync_model
    chat = ui.chat(custom_model)

    def capture_send_message(message: dict, buffers):  # noqa: ARG001
        sent_messages.append(message)

    chat._send_message = capture_send_message

    request = SendMessageRequest(
        messages=[ChatMessage(role="user", content="Hello")],
        config=ChatModelConfig(),
    )
    response = await chat._send_prompt(request)
    assert response is None

    message_id = sent_messages[0]["message_id"]
    assert sent_messages == [
        {
            "type": "stream_chunk",
            "message_id": message_id,
            "content": {"type": "text-start", "id": "text-1"},
            "is_final": False,
        },
        {
            "type": "stream_chunk",
            "message_id": message_id,
            "content": {
                "type": "text-delta",
                "id": "text-1",
                "delta": "Hello",
            },
            "is_final": False,
        },
        {
            "type": "stream_chunk",
            "message_id": message_id,
            "content": {"type": "text-end", "id": "text-1"},
            "is_final": False,
        },
        {
            "type": "stream_chunk",
            "message_id": message_id,
            "content": None,
            "is_final": True,
        },
    ]


@pytest.mark.skipif(
    not DependencyManager.pydantic_ai.has(),
    reason="Pydantic AI is not installed",
)
def test_convert_value_with_parts():
    """Test _convert_value with message parts."""
    from pydantic_ai.ui.vercel_ai.request_types import TextUIPart

    def mock_model(
        messages: list[ChatMessage], config: ChatModelConfig
    ) -> str:
        del messages, config
        return "Mock response"

    chat = ui.chat(mock_model)

    value = {
        "messages": [
            {
                "id": "msg-1",
                "role": "user",
                "parts": [{"type": "text", "text": "Hello"}],
            },
            {
                "id": "msg-2",
                "role": "assistant",
                "parts": [{"type": "text", "text": "Hi there!"}],
            },
        ]
    }

    converted = chat._convert_value(value)
    assert converted == [
        ChatMessage(
            role="user",
            id="msg-1",
            parts=[TextUIPart(type="text", text="Hello")],  # type: ignore
            content=None,
        ),
        ChatMessage(
            role="assistant",
            id="msg-2",
            parts=[TextUIPart(type="text", text="Hi there!")],  # type: ignore
            content=None,
        ),
    ]


@pytest.mark.skipif(
    not DependencyManager.pydantic_ai.has(),
    reason="Pydantic AI is not installed",
)
def test_convert_value_single_message_with_parts():
    """Test _convert_value with a single message containing parts."""
    from pydantic_ai.ui.vercel_ai.request_types import TextUIPart

    def mock_model(
        messages: list[ChatMessage], config: ChatModelConfig
    ) -> str:
        del messages, config
        return "Mock response"

    chat = ui.chat(mock_model)

    value = {
        "messages": [
            {
                "id": "msg-1",
                "role": "user",
                "parts": [{"type": "text", "text": "Hello"}],
            },
        ]
    }

    converted = chat._convert_value(value)
    assert converted == [
        ChatMessage(
            role="user",
            id="msg-1",
            parts=[TextUIPart(type="text", text="Hello")],  # type: ignore
            content=None,
        )
    ]


@pytest.mark.skipif(
    not DependencyManager.pydantic_ai.has(),
    reason="We use Pydantic to check for vercel parts",
)
def test_convert_value_with_missing_parts():
    """Test _convert_value with message missing parts field."""

    def mock_model(
        messages: list[ChatMessage], config: ChatModelConfig
    ) -> str:
        del messages, config
        return "Mock response"

    chat = ui.chat(mock_model)

    # Message without parts
    value = {"messages": [{"role": "user", "id": ""}]}

    converted = chat._convert_value(value)
    assert converted == [
        ChatMessage(id="", role="user", parts=[], content=None)
    ]


async def test_streaming_with_dict_chunks():
    """Test that streaming sends dict chunks correctly."""

    # Chunks are dicts (like from pydantic_ai vercel response types)
    chunk1 = {"type": "text-delta", "textDelta": "Hello"}
    chunk2 = {"type": "text-delta", "textDelta": " world"}

    async def mock_dict_generator():
        """Mock async generator yielding dict chunks."""
        yield chunk1
        yield chunk2

    def mock_model(
        messages: list[ChatMessage], config: ChatModelConfig
    ) -> str:
        del messages, config
        return "Mock response"

    chat = ui.chat(mock_model)

    sent_messages: list[dict] = []

    def capture_send_message(message: dict, buffers):  # noqa: ARG001
        sent_messages.append(message)

    chat._send_message = capture_send_message

    result = await chat._handle_streaming_response(mock_dict_generator())

    # Result should be None
    assert result is None

    assert sent_messages == [
        {
            "type": "stream_chunk",
            "message_id": sent_messages[0]["message_id"],
            "content": chunk1,
            "is_final": False,
        },
        {
            "type": "stream_chunk",
            "content": chunk2,
            "is_final": False,
            "message_id": sent_messages[1]["message_id"],
        },
        {
            "type": "stream_chunk",
            "message_id": sent_messages[2]["message_id"],
            "content": None,
            "is_final": True,
        },
    ]


async def test_chat_value_sync_non_generator():
    """Test chat.value with sync model returning text (non-generator)."""

    def mock_model(
        messages: list[ChatMessage], config: ChatModelConfig
    ) -> str:
        del config
        return f"Response to: {messages[-1].content}"

    chat = ui.chat(mock_model)
    assert chat.value == []

    sent_messages: list[dict] = []

    def capture_send_message(message: dict, buffers):  # noqa: ARG001
        sent_messages.append(message)

    chat._send_message = capture_send_message

    request = SendMessageRequest(
        messages=[ChatMessage(role="user", content="Hello")],
        config=ChatModelConfig(),
    )
    response = await chat._send_prompt(request)

    # Non-streaming now also returns None
    assert response is None

    # Verify proper messages were sent
    assert_single_message(sent_messages, "Response to: Hello")

    # Verify chat.value contains both user and assistant messages
    assert len(chat.value) == 2
    assert chat.value[0].role == "user"
    assert chat.value[0].content == "Hello"
    assert chat.value[1].role == "assistant"
    assert chat.value[1].content == "Response to: Hello"


async def test_chat_value_sync_non_generator_with_rich_object():
    """Test chat.value with sync model returning rich object (non-generator)."""

    class RichObject:
        def __init__(self, text: str):
            self.text = text

        def __str__(self):
            return f"Response to: {self.text}"

    def mock_model(
        messages: list[ChatMessage], config: ChatModelConfig
    ) -> RichObject:
        del config, messages
        return RichObject("Hello")

    chat = ui.chat(mock_model)
    assert chat.value == []

    sent_messages: list[dict] = []

    def capture_send_message(message: dict, buffers):  # noqa: ARG001
        sent_messages.append(message)

    chat._send_message = capture_send_message

    request = SendMessageRequest(
        messages=[ChatMessage(role="user", content="Hello", id="msg-1")],
        config=ChatModelConfig(),
    )
    response = await chat._send_prompt(request)

    # Non-streaming now also returns None
    assert response is None

    # Verify proper messages were sent (rich object is converted to HTML)
    assert_single_message(
        sent_messages, "<span>Response to: Hello</span>", use_contains=True
    )

    # Verify chat.value contains both user and assistant messages
    assert len(chat.value) == 2
    assert chat.value[0].role == "user"
    assert chat.value[0].content == "Hello"
    assert chat.value[1].role == "assistant"
    assert isinstance(chat.value[1].content, RichObject)

    msg_id_1 = chat.value[0].id
    msg_id_2 = chat.value[1].id
    assert msg_id_1
    assert msg_id_2

    # Simulate the frontend sending back the message
    converted = chat._convert_value(
        {
            "messages": [
                {
                    "id": msg_id_1,
                    "role": "user",
                    "content": "Hello",
                },
                {
                    "id": msg_id_2,
                    "role": "assistant",
                    "content": "Response to: Hello",
                },
            ]
        }
    )

    # Verify chat.value still contains the rich object
    assert len(converted) == 2
    assert converted[0].role == "user"
    assert converted[0].content == "Hello"
    assert converted[0].id == msg_id_1
    assert converted[1].role == "assistant"
    assert converted[1].id == msg_id_2
    assert isinstance(converted[1].content, RichObject)


async def test_chat_value_async_non_generator():
    """Test chat.value with async model returning text (non-generator)."""

    async def mock_model(
        messages: list[ChatMessage], config: ChatModelConfig
    ) -> str:
        del config
        await asyncio.sleep(0.01)
        return f"Async response to: {messages[-1].content}"

    chat = ui.chat(mock_model)
    assert chat.value == []

    sent_messages: list[dict] = []

    def capture_send_message(message: dict, buffers):  # noqa: ARG001
        sent_messages.append(message)

    chat._send_message = capture_send_message

    request = SendMessageRequest(
        messages=[ChatMessage(role="user", content="Test message")],
        config=ChatModelConfig(),
    )
    response = await chat._send_prompt(request)

    # Non-streaming now also returns None
    assert response is None

    # Verify proper messages were sent
    assert_single_message(sent_messages, "Async response to: Test message")

    # Verify chat.value contains both user and assistant messages
    assert len(chat.value) == 2
    assert chat.value[0].role == "user"
    assert chat.value[0].content == "Test message"
    assert chat.value[1].role == "assistant"
    assert chat.value[1].content == "Async response to: Test message"


async def test_chat_value_sync_generator_text():
    """Test chat.value with sync generator yielding text chunks."""

    def mock_streaming_model(
        messages: list[ChatMessage], config: ChatModelConfig
    ):
        del messages, config
        yield "Hello"
        yield " "
        yield "world"

    chat = ui.chat(mock_streaming_model)
    assert chat.value == []

    # Mock _send_message to avoid needing kernel context
    chat._send_message = lambda message, buffers: None  # noqa: ARG005

    request = SendMessageRequest(
        messages=[ChatMessage(role="user", content="Stream this")],
        config=ChatModelConfig(),
    )
    response = await chat._send_prompt(request)

    # Streaming returns None
    assert response is None

    # String generators now update chat history with accumulated text
    assert len(chat._chat_history) == 2
    assert chat._chat_history[0].role == "user"
    assert chat._chat_history[0].content == "Stream this"
    assert chat._chat_history[1].role == "assistant"
    assert chat._chat_history[1].content == "Hello world"

    # Verify value also contains both messages
    assert len(chat.value) == 2
    assert chat.value[0].role == "user"
    assert chat.value[1].role == "assistant"
    assert chat.value[1].content == "Hello world"


async def test_chat_value_async_generator_text():
    """Test chat.value with async generator yielding text chunks."""

    async def mock_streaming_model(
        messages: list[ChatMessage], config: ChatModelConfig
    ):
        del messages, config
        for word in ["Async", " ", "streaming"]:
            await asyncio.sleep(0.001)
            yield word

    chat = ui.chat(mock_streaming_model)
    assert chat.value == []

    # Mock _send_message to avoid needing kernel context
    chat._send_message = lambda message, buffers: None  # noqa: ARG005

    request = SendMessageRequest(
        messages=[ChatMessage(role="user", content="Stream async")],
        config=ChatModelConfig(),
    )
    response = await chat._send_prompt(request)

    # Streaming returns None
    assert response is None

    # String generators now update chat history with accumulated text
    assert len(chat._chat_history) == 2
    assert chat._chat_history[0].role == "user"
    assert chat._chat_history[0].content == "Stream async"
    assert chat._chat_history[1].role == "assistant"
    assert chat._chat_history[1].content == "Async streaming"

    # Verify value also contains both messages
    assert len(chat.value) == 2
    assert chat.value[0].role == "user"
    assert chat.value[1].role == "assistant"
    assert chat.value[1].content == "Async streaming"


async def test_chat_value_sync_generator_dicts():
    """Test chat.value with sync generator yielding dict chunks."""

    def mock_streaming_model(
        messages: list[ChatMessage], config: ChatModelConfig
    ):
        del messages, config
        yield {"type": "text-start", "id": "text-1"}
        yield {"type": "text-delta", "id": "text-1", "delta": "Dict"}
        yield {"type": "text-delta", "id": "text-1", "delta": " chunks"}
        yield {"type": "text-end", "id": "text-1"}

    chat = ui.chat(mock_streaming_model)
    assert chat.value == []

    # Mock _send_message to avoid needing kernel context
    chat._send_message = lambda message, buffers: None  # noqa: ARG005

    request = SendMessageRequest(
        messages=[ChatMessage(role="user", content="Send dicts")],
        config=ChatModelConfig(),
    )
    response = await chat._send_prompt(request)

    # Streaming returns None
    assert response is None

    # Verify chat._chat_history contains the user message
    # (streaming responses with dicts are managed by frontend)
    assert len(chat._chat_history) == 1
    assert chat._chat_history[0].role == "user"
    assert chat._chat_history[0].content == "Send dicts"

    # Verify value is empty (until the frontend sends back the message)
    assert chat.value == []


async def test_chat_value_async_generator_dicts():
    """Test chat.value with async generator yielding dict chunks."""

    async def mock_streaming_model(
        messages: list[ChatMessage], config: ChatModelConfig
    ):
        del messages, config
        chunks = [
            {"type": "text-start", "id": "text-1"},
            {"type": "text-delta", "id": "text-1", "delta": "Async"},
            {"type": "text-delta", "id": "text-1", "delta": " dict"},
            {"type": "text-end", "id": "text-1"},
        ]
        for chunk in chunks:
            await asyncio.sleep(0.001)
            yield chunk

    chat = ui.chat(mock_streaming_model)
    assert chat.value == []

    # Mock _send_message to avoid needing kernel context
    chat._send_message = lambda message, buffers: None  # noqa: ARG005

    request = SendMessageRequest(
        messages=[ChatMessage(role="user", content="Send async dicts")],
        config=ChatModelConfig(),
    )
    response = await chat._send_prompt(request)

    # Streaming returns None
    assert response is None

    # Verify chat._chat_history contains the user message
    # (streaming responses with dicts are managed by frontend)
    assert len(chat._chat_history) == 1
    assert chat._chat_history[0].role == "user"
    assert chat._chat_history[0].content == "Send async dicts"

    # Verify value is empty (until the frontend sends back the message)
    assert chat.value == []


async def test_chat_value_multiple_exchanges():
    """Test chat.value accumulates messages across multiple exchanges."""

    def mock_model(
        messages: list[ChatMessage], config: ChatModelConfig
    ) -> str:
        del config
        # Echo back the last user message
        return f"Echo: {messages[-1].content}"

    chat = ui.chat(mock_model)
    assert chat.value == []

    # First exchange
    request1 = SendMessageRequest(
        messages=[ChatMessage(role="user", content="First")],
        config=ChatModelConfig(),
    )
    await chat._send_prompt(request1)

    assert len(chat.value) == 2
    assert chat.value[0].content == "First"
    assert chat.value[1].content == "Echo: First"

    # Second exchange - chat history accumulates
    request2 = SendMessageRequest(
        messages=[
            ChatMessage(role="user", content="First"),
            ChatMessage(role="assistant", content="Echo: First"),
            ChatMessage(role="user", content="Second"),
        ],
        config=ChatModelConfig(),
    )
    await chat._send_prompt(request2)

    assert len(chat.value) == 4
    assert chat.value[2].content == "Second"
    assert chat.value[3].content == "Echo: Second"
