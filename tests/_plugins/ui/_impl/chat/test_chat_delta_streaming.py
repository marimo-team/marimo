# Copyright 2026 Marimo. All rights reserved.
"""Tests for delta-based streaming in chat UI.

The streaming implementation uses the Vercel AI SDK protocol:
- text-start: Begins a text stream with an id
- text-delta: Contains incremental text content
- text-end: Marks the end of a text stream
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator

from marimo._ai._types import ChatMessage
from marimo._plugins.ui._impl.chat.chat import chat


def extract_deltas(sent_messages: list[dict[str, Any]]) -> list[str]:
    """Extract delta text from Vercel AI SDK format messages."""
    deltas = []
    for msg in sent_messages:
        content = msg.get("content")
        if isinstance(content, dict) and content.get("type") == "text-delta":
            deltas.append(content.get("delta", ""))
    return deltas


def get_accumulated_text(sent_messages: list[dict[str, Any]]) -> str:
    """Get the accumulated text from all deltas."""
    return "".join(extract_deltas(sent_messages))


class TestDeltaStreaming:
    """Test delta-based streaming mode using Vercel AI SDK protocol."""

    async def test_async_delta_streaming_sends_vercel_chunks(self):
        """Test that async generators send Vercel AI SDK format chunks."""

        async def delta_generator() -> AsyncGenerator[str, None]:
            """Yields individual delta chunks."""
            yield "Hello"
            yield " "
            yield "world"
            yield "!"

        chat_ui = chat(delta_generator)
        sent_messages: list[dict[str, Any]] = []

        def capture_send(msg: dict[str, Any], **kwargs: object) -> None:
            del kwargs  # Unused
            sent_messages.append(msg)

        chat_ui._send_message = capture_send  # type: ignore

        # Handle the streaming response (returns None in new implementation)
        result = await chat_ui._handle_streaming_response(delta_generator())

        # New implementation returns None (frontend manages state)
        assert result is None

        # Verify Vercel AI SDK format: text-start, text-delta(s), text-end, final
        content_types = [
            msg["content"]["type"]
            for msg in sent_messages
            if isinstance(msg.get("content"), dict)
        ]
        assert content_types[0] == "text-start"
        assert all(t == "text-delta" for t in content_types[1:-1])
        assert content_types[-1] == "text-end"

        # Verify accumulated text from deltas
        accumulated = get_accumulated_text(sent_messages)
        assert accumulated == "Hello world!"

        # Final message should have is_final=True
        assert sent_messages[-1]["is_final"] is True

    async def test_sync_delta_streaming_sends_vercel_chunks(self):
        """Test that sync generators send Vercel AI SDK format chunks."""

        def delta_generator() -> Generator[str, None, None]:
            """Yields individual delta chunks."""
            yield "One"
            yield " "
            yield "Two"
            yield " "
            yield "Three"

        chat_ui = chat(delta_generator)
        sent_messages: list[dict[str, Any]] = []

        def capture_send(msg: dict[str, Any], **kwargs: object) -> None:
            del kwargs  # Unused
            sent_messages.append(msg)

        chat_ui._send_message = capture_send  # type: ignore

        result = await chat_ui._handle_streaming_response(delta_generator())

        assert result is None
        accumulated = get_accumulated_text(sent_messages)
        assert accumulated == "One Two Three"

    async def test_empty_delta_handled(self):
        """Test that empty deltas are handled gracefully."""

        async def delta_generator() -> AsyncGenerator[str, None]:
            """Yields some empty deltas."""
            yield "Hello"
            yield ""  # Empty delta
            yield " "
            yield ""  # Another empty delta
            yield "world"

        chat_ui = chat(delta_generator)
        sent_messages: list[dict[str, Any]] = []

        def capture_send(msg: dict[str, Any], **kwargs: object) -> None:
            del kwargs  # Unused
            sent_messages.append(msg)

        chat_ui._send_message = capture_send  # type: ignore

        result = await chat_ui._handle_streaming_response(delta_generator())

        assert result is None
        # Empty deltas are still sent as text-delta chunks
        deltas = extract_deltas(sent_messages)
        assert deltas == ["Hello", "", " ", "", "world"]
        assert get_accumulated_text(sent_messages) == "Hello world"

    async def test_single_delta(self):
        """Test streaming with a single delta."""

        async def delta_generator() -> AsyncGenerator[str, None]:
            yield "Single chunk"

        chat_ui = chat(delta_generator)
        sent_messages: list[dict[str, Any]] = []

        def capture_send(msg: dict[str, Any], **kwargs: object) -> None:
            del kwargs  # Unused
            sent_messages.append(msg)

        chat_ui._send_message = capture_send  # type: ignore

        result = await chat_ui._handle_streaming_response(delta_generator())

        assert result is None
        assert get_accumulated_text(sent_messages) == "Single chunk"

        # Should have: text-start, text-delta, text-end, final
        assert len(sent_messages) == 4
        assert sent_messages[-1]["is_final"] is True

    async def test_no_deltas(self):
        """Test streaming with no deltas (empty generator)."""

        async def delta_generator() -> AsyncGenerator[str, None]:
            # Yield nothing
            if False:
                yield ""

        chat_ui = chat(delta_generator)
        sent_messages: list[dict[str, Any]] = []

        def capture_send(msg: dict[str, Any], **kwargs: object) -> None:
            del kwargs  # Unused
            sent_messages.append(msg)

        chat_ui._send_message = capture_send  # type: ignore

        result = await chat_ui._handle_streaming_response(delta_generator())

        assert result is None
        # Should only have the final message (no text-start/end since no text)
        assert len(sent_messages) == 1
        assert sent_messages[0]["is_final"] is True

    async def test_unicode_deltas(self):
        """Test that unicode characters in deltas are handled correctly."""

        async def delta_generator() -> AsyncGenerator[str, None]:
            yield "Hello "
            yield "🌍"
            yield " "
            yield "世界"
            yield "!"

        chat_ui = chat(delta_generator)
        sent_messages: list[dict[str, Any]] = []

        def capture_send(msg: dict[str, Any], **kwargs: object) -> None:
            del kwargs  # Unused
            sent_messages.append(msg)

        chat_ui._send_message = capture_send  # type: ignore

        result = await chat_ui._handle_streaming_response(delta_generator())

        assert result is None
        assert get_accumulated_text(sent_messages) == "Hello 🌍 世界!"

    async def test_message_id_consistency(self):
        """Test that all chunks in a stream share the same message_id."""

        async def delta_generator() -> AsyncGenerator[str, None]:
            yield "A"
            yield "B"
            yield "C"

        chat_ui = chat(delta_generator)
        sent_messages: list[dict[str, Any]] = []

        def capture_send(msg: dict[str, Any], **kwargs: object) -> None:
            del kwargs  # Unused
            sent_messages.append(msg)

        chat_ui._send_message = capture_send  # type: ignore

        await chat_ui._handle_streaming_response(delta_generator())

        # All messages should have the same message_id
        message_ids = [msg["message_id"] for msg in sent_messages]
        assert len(set(message_ids)) == 1
        assert all(msg["type"] == "stream_chunk" for msg in sent_messages)

    async def test_long_streaming_response(self):
        """Test streaming with many small deltas (simulates real AI streaming)."""

        async def delta_generator() -> AsyncGenerator[str, None]:
            # Simulate many small tokens like real AI models
            words = [
                "This",
                " is",
                " a",
                " long",
                " streaming",
                " response",
                " with",
                " many",
                " deltas",
                ".",
            ]
            for word in words:
                yield word
                await asyncio.sleep(0.001)  # Tiny delay

        chat_ui = chat(delta_generator)
        sent_messages: list[dict[str, Any]] = []

        def capture_send(msg: dict[str, Any], **kwargs: object) -> None:
            del kwargs  # Unused
            sent_messages.append(msg)

        chat_ui._send_message = capture_send  # type: ignore

        result = await chat_ui._handle_streaming_response(delta_generator())

        assert result is None
        expected = "This is a long streaming response with many deltas."
        assert get_accumulated_text(sent_messages) == expected

        # Verify deltas are individual words
        deltas = extract_deltas(sent_messages)
        assert deltas == [
            "This",
            " is",
            " a",
            " long",
            " streaming",
            " response",
            " with",
            " many",
            " deltas",
            ".",
        ]


class TestStreamingWithChatModels:
    """Test streaming with actual ChatModel-like objects."""

    async def test_custom_model_function(self):
        """Test that custom model functions work with delta streaming."""

        async def custom_model(
            messages: list[ChatMessage],
            config: dict[str, Any],  # noqa: ARG001
        ) -> AsyncGenerator[str, None]:
            """Custom model that yields deltas."""
            user_msg = messages[-1].content
            response = f"You said: {user_msg}"
            for char in response:
                yield char
                await asyncio.sleep(0.001)

        chat_ui = chat(custom_model)
        sent_messages: list[dict[str, Any]] = []

        def capture_send(msg: dict[str, Any], **kwargs: object) -> None:
            del kwargs  # Unused
            sent_messages.append(msg)

        chat_ui._send_message = capture_send  # type: ignore

        # Simulate calling the model
        test_messages = [ChatMessage(role="user", content="Hello")]
        generator = custom_model(test_messages, {})

        result = await chat_ui._handle_streaming_response(generator)

        assert result is None
        assert get_accumulated_text(sent_messages) == "You said: Hello"
        assert sent_messages[-1]["is_final"] is True


class TestStreamingEfficiency:
    """Test that delta streaming is efficient."""

    async def test_delta_streaming_sends_individual_chunks(self):
        """Verify delta streaming sends individual chunks, not accumulated."""

        # Simulate 100-word response
        words = ["word" + str(i) for i in range(100)]

        async def delta_stream() -> AsyncGenerator[str, None]:
            for word in words:
                yield word + " "

        chat_ui = chat(delta_stream)
        sent_messages: list[dict[str, Any]] = []

        def capture_delta(msg: dict[str, Any], **kwargs: object) -> None:
            del kwargs  # Unused
            sent_messages.append(msg)

        chat_ui._send_message = capture_delta  # type: ignore

        await chat_ui._handle_streaming_response(delta_stream())

        # Extract all deltas sent
        deltas = extract_deltas(sent_messages)

        # Each delta should be a single word (not accumulated)
        assert len(deltas) == 100
        assert deltas[0] == "word0 "
        assert deltas[1] == "word1 "  # NOT "word0 word1 "
        assert deltas[99] == "word99 "

        # Total accumulated text should be all words
        accumulated = get_accumulated_text(sent_messages)
        assert accumulated == " ".join(words) + " "
